"""Reconstrucción de la evolución diaria hacia atrás.

La app sólo guarda un snapshot por día desde que empezó a correr. Para ver la
evolución de antes se parte de las tenencias actuales y se deshacen las
operaciones hacia atrás (compras suman, ventas restan) para saber la cantidad
de cada activo cada día; esa cantidad se valúa con la serie histórica de
precios de IOL. Los snapshots así generados quedan con source="reconstruido" y
nunca pisan uno real.

Para que una unidad de precio rara (bonos cotizan cada 100 VN) no distorsione,
cada posición se calibra contra la valuación actual de IOL: factor = valuación
de hoy / (cantidad × último precio de la serie).

Los FCI no tienen serie en IOL: se valúan a la cuotaparte de hoy (valor plano
salvo suscripciones y rescates), así que su rendimiento pasado queda en cero.
"""
from __future__ import annotations

import bisect
import logging
import re
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..models import Holding, Operation, PortfolioSnapshot
from .classifier import _INTRINSIC_SUFFIX_TICKERS, classify_asset
from .dolar_service import backfill_historical_mep, build_mep_lookup, fx_for_date
from .iol_client import IolClient
from .ons_whitelist import normalize_ticker

log = logging.getLogger(__name__)

RECONSTRUCTED_SOURCE = "reconstruido"

_BUY = ("COMPRA", "SUSCRIPCION")
_SELL = ("VENTA", "RESCATE")
_PER_100_CLASSES = ("Bono", "ON", "Letra")
_IOL_MARKETS = {"argentina": ("bCBA",), "estados_unidos": ("nYSE", "nASDAQ", "aMEX")}
_USD_MARKER = re.compile(r"\s+(US\$|USD|U\$S)$", re.IGNORECASE)


def _f(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _base(simbolo: str) -> str:
    """Símbolo sin sufijo de moneda (AL30D → AL30, YM34O → YM34); respeta KO, YPFD, etc."""
    s = _USD_MARKER.sub("", (simbolo or "").upper().strip())
    if s in _INTRINSIC_SUFFIX_TICKERS:
        return s
    return normalize_ticker(s)[0]


def _is_usd(currency_kind: str | None) -> bool:
    return currency_kind in ("USD_MEP", "USD_CABLE")


@dataclass
class _Position:
    simbolo: str
    mercado: str  # argentina | estados_unidos
    clase: str
    native: str  # ARS | USD
    qty_now: float = 0.0
    value_now: float = 0.0  # en moneda nativa
    ops: list = field(default_factory=list)
    price_dates: list = field(default_factory=list)
    prices: list = field(default_factory=list)
    factor: float | None = None
    unit_flat: float | None = None  # valor por unidad cuando no hay serie

    def has_series(self) -> bool:
        return bool(self.prices) and self.factor is not None

    def price_at(self, d: date) -> float | None:
        """Último precio de la serie a la fecha (o el primero posterior si no hay previo)."""
        if not self.price_dates:
            return None
        i = bisect.bisect_right(self.price_dates, d)
        return self.prices[i - 1] if i > 0 else self.prices[0]

    def unit_value(self, d: date) -> float | None:
        if self.has_series():
            p = self.price_at(d)
            return p * self.factor if p else None
        return self.unit_flat


def _parse_series(rows: list) -> tuple[list, list]:
    by_day: dict[date, tuple[str, float]] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        price = _f(r.get("ultimoPrecio") or r.get("cierre"))
        stamp = str(r.get("fechaHora") or r.get("fecha") or "")
        try:
            d = date.fromisoformat(stamp[:10])
        except ValueError:
            continue
        if price <= 0:
            continue
        # Puede haber más de una fila por día: vale la de hora más tardía
        if d not in by_day or stamp > by_day[d][0]:
            by_day[d] = (stamp, price)
    dates = sorted(by_day)
    return dates, [by_day[d][1] for d in dates]


def _op_amount_native(op: Operation, native: str, mep: dict, mep_dates: list) -> float:
    amount = abs(_f(op.monto_neto) or _f(op.monto_operado))
    op_usd = _is_usd(op.currency_kind)
    if (native == "USD") == op_usd:
        return amount
    rate = fx_for_date(mep, mep_dates, op.fecha_operada) if op.fecha_operada else None
    if not rate:
        return 0.0
    return amount / rate if native == "USD" else amount * rate


def _build_positions(holdings: list[Holding], ops: list[Operation]) -> list[_Position]:
    positions: dict[str, _Position] = {}
    by_base: dict[str, str] = {}
    for h in holdings:
        native = "USD" if any(k in (h.moneda or "").lower() for k in ("dolar", "usd")) else "ARS"
        value = _f(h.valuacion_usd) if native == "USD" else _f(h.valuacion_ars)
        key = f"{h.mercado}:{h.simbolo}"
        positions[key] = _Position(
            simbolo=h.simbolo, mercado=h.mercado, clase=h.clase, native=native,
            qty_now=_f(h.cantidad), value_now=value,
        )
        if h.clase != "FCI":
            by_base.setdefault(_base(h.simbolo), key)

    exact = {p.simbolo.upper(): k for k, p in positions.items()}
    orphans: dict[str, list[Operation]] = {}
    for op in ops:
        sym = (op.simbolo or "").upper().strip()
        if not sym:
            continue
        key = exact.get(sym) or by_base.get(_base(sym))
        if key:
            positions[key].ops.append(op)
        else:
            orphans.setdefault(_base(sym), []).append(op)

    # Posiciones que ya no están en la cartera (vendidas o vencidas en el período)
    for base, group in orphans.items():
        pesos = [o for o in group if not _is_usd(o.currency_kind)]
        ref = (pesos or group)[0]
        mercado_raw = (ref.mercado or "").lower()
        mercado = "estados_unidos" if any(m in mercado_raw for m in ("nyse", "nasdaq", "amex")) else "argentina"
        positions[f"~{base}"] = _Position(
            simbolo=ref.simbolo,
            mercado=mercado,
            clase=classify_asset(simbolo=ref.simbolo, tipo=None, descripcion=ref.descripcion, mercado=ref.mercado),
            native="USD" if _is_usd(ref.currency_kind) else "ARS",
            ops=group,
        )
    return list(positions.values())


def _calibrate(p: _Position, today: date) -> None:
    """Factor precio-de-serie → valor por unidad, y valor plano de respaldo."""
    if p.qty_now > 0 and p.value_now > 0:
        p.unit_flat = p.value_now / p.qty_now
        last = p.price_at(today)
        if last:
            p.factor = p.value_now / (p.qty_now * last)
        return
    # Sin tenencia actual: la unidad sale de las propias operaciones
    ratios, units = [], []
    for o in p.ops:
        qty, price, monto = _f(o.cantidad), _f(o.precio), abs(_f(o.monto_operado))
        if qty > 0 and monto > 0:
            units.append(monto / qty)
            if price > 0:
                ratios.append(monto / (qty * price))
    if p.prices:
        p.factor = statistics.median(ratios) if ratios else (0.01 if p.clase in _PER_100_CLASSES else 1.0)
    if units:
        p.unit_flat = statistics.median(units)


async def _fetch_series(client: IolClient, p: _Position, desde: date, hasta: date) -> None:
    if p.clase == "FCI":
        return
    for mercado in _IOL_MARKETS.get(p.mercado, ("bCBA",)):
        try:
            rows = await client.get_serie_historica(mercado, p.simbolo, desde=desde, hasta=hasta)
        except Exception as e:
            log.info("serie histórica %s/%s no disponible: %s", mercado, p.simbolo, e)
            continue
        dates, prices = _parse_series(rows)
        if dates:
            p.price_dates, p.prices = dates, prices
            return


async def reconstruct_snapshots(db: Session, user_id: int, *, dias: int = 365) -> dict:
    today = date.today()
    desde = today - timedelta(days=dias)
    hasta = today - timedelta(days=1)

    holdings = (
        db.query(Holding).filter(Holding.user_id == user_id, Holding.clase != "Caucion").all()
    )
    ops = (
        db.query(Operation)
        .filter(
            Operation.user_id == user_id,
            Operation.fecha_operada > desde,
            Operation.event_kind.in_(_BUY + _SELL),
        )
        .all()
    )
    positions = _build_positions(holdings, ops)

    # Precios desde un poco antes para tener valor el primer día aunque sea feriado
    async with IolClient(db, user_id) as client:
        for p in positions:
            await _fetch_series(client, p, desde - timedelta(days=10), today)

    await backfill_historical_mep(db, desde=desde - timedelta(days=10), hasta=today)
    mep = build_mep_lookup(db, desde, today)
    mep_dates = sorted(mep)

    for p in positions:
        _calibrate(p, today)

    # Cambio de cantidad de cada operación (+ compra, − venta)
    deltas: list[list[tuple[date, float]]] = []
    for p in positions:
        moves = []
        for o in p.ops:
            qty = _f(o.cantidad)
            if p.clase == "FCI" or qty <= 0:
                # FCI: la cantidad de IOL no siempre viene en cuotapartes; se usa el monto
                unit = p.unit_value(o.fecha_operada)
                amount = _op_amount_native(o, p.native, mep, mep_dates)
                qty = amount / unit if unit and amount else 0.0
            sign = 1 if o.event_kind in _BUY else -1
            moves.append((o.fecha_operada, sign * qty))
        deltas.append(moves)

    series_days = {d for p in positions for d in p.price_dates if desde <= d <= hasta}
    days = sorted(series_days) or [
        desde + timedelta(days=i)
        for i in range((hasta - desde).days + 1)
        if (desde + timedelta(days=i)).weekday() < 5
    ]

    existing = {
        s.date: s
        for s in db.query(PortfolioSnapshot).filter(
            PortfolioSnapshot.user_id == user_id,
            PortfolioSnapshot.date >= desde,
            PortfolioSnapshot.date <= hasta,
        )
    }

    created = updated = 0
    for d in days:
        prev = existing.get(d)
        if prev is not None and prev.source != RECONSTRUCTED_SOURCE:
            continue  # nunca se pisa un snapshot real
        rate = fx_for_date(mep, mep_dates, d)
        if not rate:
            continue
        breakdown = []
        total_ars = total_usd = 0.0
        for p, moves in zip(positions, deltas):
            qty = p.qty_now - sum(dq for fecha, dq in moves if fecha and fecha > d)
            unit = p.unit_value(d)
            if qty <= 1e-9 or not unit:
                continue
            value = qty * unit
            v_ars, v_usd = (value * rate, value) if p.native == "USD" else (value, value / rate)
            total_ars += v_ars
            total_usd += v_usd
            breakdown.append({
                "simbolo": p.simbolo,
                "clase": p.clase,
                "mercado": p.mercado,
                "cantidad": round(qty, 6),
                "ultimo_precio": round(p.price_at(d) if p.has_series() else unit, 6),
                "valuacion_ars": round(v_ars, 2),
                "valuacion_usd": round(v_usd, 2),
            })
        if total_ars <= 0:
            continue
        row = prev or PortfolioSnapshot(user_id=user_id, date=d)
        if prev is None:
            db.add(row)
            created += 1
        else:
            updated += 1
        row.taken_at = datetime.now(tz=timezone.utc)
        row.total_ars = round(total_ars, 2)
        row.total_usd = round(total_usd, 2)
        row.dolar_rate = rate
        row.dolar_source = "MEP"
        row.breakdown_json = breakdown
        row.source = RECONSTRUCTED_SOURCE
    db.commit()

    sin_serie = sorted(p.simbolo for p in positions if not p.has_series() and p.unit_flat)
    log.info(
        "reconstruct_snapshots: user=%d creados=%d actualizados=%d posiciones=%d sin_serie=%s",
        user_id, created, updated, len(positions), sin_serie,
    )
    return {
        "creados": created,
        "actualizados": updated,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "sin_serie": sin_serie,
    }
