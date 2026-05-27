"""Portfolio service: refresh holdings from IOL + compute KPIs."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy.orm import Session

from datetime import timedelta

from ..models import Holding, Operation, PortfolioSnapshot
from . import dolar_service
from .classifier import classify_asset
from .dolar_service import build_mep_lookup, fx_for_date
from .iol_client import IolClient

log = logging.getLogger(__name__)


def _first_not_none(*vals):
    """Return the first non-None value as float, or None if all are None."""
    for v in vals:
        if v is not None:
            return _f(v)
    return None


def _f(v) -> float:
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _iter_titulos(portafolio: dict) -> Iterable[dict]:
    """IOL portafolio shape (tolerant): {'pais': ..., 'activos': [{ 'titulo': {...}, 'cantidad', 'valorizado', 'ultimoPrecio', 'ppc', ... }, ...]}."""
    if not isinstance(portafolio, dict):
        return []
    activos = portafolio.get("activos") or portafolio.get("Activos") or []
    return activos if isinstance(activos, list) else []


def _extract_row(activo: dict, mercado: str) -> dict | None:
    titulo = activo.get("titulo") or activo.get("Titulo") or {}
    simbolo = titulo.get("simbolo") or titulo.get("Simbolo") or activo.get("simbolo")
    if not simbolo:
        return None
    log.debug("IOL activo keys=%s titulo keys=%s", list(activo.keys()), list(titulo.keys()))
    descripcion = titulo.get("descripcion") or activo.get("descripcion")
    tipo_raw = titulo.get("tipo") or activo.get("tipo")
    moneda = (
        titulo.get("moneda")
        or activo.get("moneda")
        or activo.get("monedaCotizacion")
    )

    return {
        "simbolo": simbolo,
        "descripcion": descripcion,
        "tipo": tipo_raw,
        "clase": classify_asset(
            simbolo=simbolo, tipo=tipo_raw, descripcion=descripcion, mercado=mercado
        ),
        "cantidad": _f(activo.get("cantidad")),
        "ppc": _f(activo.get("ppc") or activo.get("precioPromedioCompra")),
        "ultimo_precio": _f(activo.get("ultimoPrecio") or titulo.get("ultimoPrecio")),
        "valuacion": _f(
            activo.get("valorizado")
            or activo.get("valuacionActual")
            or activo.get("valuacion")
        ),
        "ganancia_porcentaje": _f(activo.get("gananciaPorcentaje")),
        "ganancia_dinero": _f(activo.get("gananciaDinero")),
        "variacion_dia": _first_not_none(
            activo.get("variacion"),
            titulo.get("variacion"),
            activo.get("variacionPorcentaje"),
            titulo.get("variacionPorcentaje"),
        ),
        "moneda": moneda,
        "mercado_iol": titulo.get("mercado") or activo.get("mercado"),
    }


async def refresh_holdings(db: Session, user_id: int) -> list[Holding]:
    """Pull both Argentina + USA portfolios, upsert into Holding."""
    async with IolClient(db, user_id) as client:
        pais_data: dict[str, dict] = {}
        for pais in ("argentina", "estados_unidos"):
            try:
                pais_data[pais] = await client.get_portafolio(pais)
            except Exception as e:
                log.warning("portafolio fetch failed pais=%s: %s", pais, e)
                pais_data[pais] = {}

        # MEP rate for ARS→USD valuation
        today = date.today()
        try:
            mep = await dolar_service.get_or_fetch(db, d=today, source="MEP")
            mep_rate = _f(mep.promedio)
        except Exception:
            mep_rate = 0.0

        keep_keys: set[tuple[str, str]] = set()
        rows: list[Holding] = []
        # simbolo → mercado_iol for cotizacion fallback
        needs_variacion: list = []

        for mercado, pf in pais_data.items():
            for activo in _iter_titulos(pf):
                row_data = _extract_row(activo, mercado)
                if row_data is None:
                    continue
                if row_data["clase"] == "Caucion":
                    log.info("refresh_holdings: skipping caucion %s", row_data["simbolo"])
                    continue
                simbolo = row_data["simbolo"]
                keep_keys.add((mercado, simbolo))
                moneda = (row_data.get("moneda") or "").lower()
                valuacion = row_data["valuacion"]
                if "dolar" in moneda or "usd" in moneda:
                    valuacion_usd = valuacion
                    valuacion_ars = valuacion * mep_rate if mep_rate else 0.0
                else:
                    valuacion_ars = valuacion
                    valuacion_usd = (valuacion / mep_rate) if mep_rate else 0.0

                holding = (
                    db.query(Holding)
                    .filter(
                        Holding.user_id == user_id,
                        Holding.mercado == mercado,
                        Holding.simbolo == simbolo,
                    )
                    .first()
                )
                if holding is None:
                    holding = Holding(user_id=user_id, mercado=mercado, simbolo=simbolo)
                    db.add(holding)

                holding.descripcion = row_data["descripcion"]
                holding.tipo = row_data["tipo"]
                holding.clase = row_data["clase"]
                holding.cantidad = row_data["cantidad"]
                holding.ppc = row_data["ppc"]
                holding.ultimo_precio = row_data["ultimo_precio"]
                holding.valuacion_ars = valuacion_ars
                holding.valuacion_usd = valuacion_usd
                holding.ganancia_porcentaje = row_data["ganancia_porcentaje"]
                holding.ganancia_dinero = row_data["ganancia_dinero"]
                new_var = row_data.get("variacion_dia")
                holding.variacion_dia = new_var
                if new_var is not None and float(new_var) != 0.0:
                    holding.variacion_dia_prev = new_var
                holding.moneda = row_data["moneda"]
                rows.append(holding)

                if holding.variacion_dia is None:
                    mercado_iol = row_data.get("mercado_iol")
                    if mercado_iol:
                        needs_variacion.append((simbolo, mercado_iol, holding))

        # Fallback: fetch individual cotizacion for holdings without daily variation
        if needs_variacion:
            log.info("variacion_dia missing for %d holdings — fetching cotizaciones", len(needs_variacion))
            for simbolo, mercado_iol, holding in needs_variacion:
                try:
                    cot = await client.get_cotizacion(mercado_iol, simbolo)
                    var = _first_not_none(
                        cot.get("variacion"),
                        cot.get("variacionPorcentaje"),
                    )
                    if var is not None:
                        holding.variacion_dia = var
                        if float(var) != 0.0:
                            holding.variacion_dia_prev = var
                        log.debug("cotizacion fallback %s variacion=%.4f", simbolo, var)
                except Exception as e:
                    log.debug("cotizacion fallback failed %s: %s", simbolo, e)

    # Drop holdings no longer in IOL portfolio
    existing = db.query(Holding).filter(Holding.user_id == user_id).all()
    for h in existing:
        if (h.mercado, h.simbolo) not in keep_keys:
            db.delete(h)

    db.commit()
    return rows


def compute_kpis(db: Session, user_id: int, *, dolar_rate: float, dolar_source: str) -> dict:
    holdings = db.query(Holding).filter(
        Holding.user_id == user_id, Holding.clase != "Caucion"
    ).all()
    total_ars = sum(_f(h.valuacion_ars) for h in holdings)
    total_usd = sum(_f(h.valuacion_usd) for h in holdings)

    # Distribución por clase
    by_clase: dict[str, dict] = {}
    for h in holdings:
        d = by_clase.setdefault(
            h.clase or "Otro", {"valor_ars": 0.0, "valor_usd": 0.0}
        )
        d["valor_ars"] += _f(h.valuacion_ars)
        d["valor_usd"] += _f(h.valuacion_usd)
    distribucion = []
    for clase, vals in sorted(by_clase.items(), key=lambda kv: -kv[1]["valor_ars"]):
        pct = (vals["valor_ars"] / total_ars * 100.0) if total_ars > 0 else 0.0
        distribucion.append(
            {
                "clase": clase,
                "valor_ars": round(vals["valor_ars"], 2),
                "valor_usd": round(vals["valor_usd"], 2),
                "pct": round(pct, 2),
            }
        )

    pnl_no_realizada_ars = sum(_f(h.ganancia_dinero) for h in holdings)
    pnl_no_realizada_usd = (pnl_no_realizada_ars / dolar_rate) if dolar_rate else 0.0

    # Dividendos / renta del 2026 desde Operations — convertido a ambas monedas via MEP histórico
    year = 2026
    ops = db.query(Operation).filter(
        Operation.user_id == user_id,
        Operation.fecha_operada >= date(year, 1, 1),
        Operation.fecha_operada <= date(year, 12, 31),
    ).all()
    mep = build_mep_lookup(db, date(year, 1, 1), date(year, 12, 31))
    sorted_mep_dates = sorted(mep.keys())

    div_ars = 0.0
    div_usd = 0.0
    renta_ars = 0.0
    renta_usd = 0.0
    amort_ars = 0.0
    amort_usd = 0.0
    n_ops_2026 = len(ops)

    for o in ops:
        amount = abs(_f(o.monto_neto) if o.monto_neto is not None else _f(o.monto_operado))
        is_usd = o.currency_kind in ("USD_MEP", "USD_CABLE")
        rate = fx_for_date(mep, sorted_mep_dates, o.fecha_operada) if o.fecha_operada else None

        if rate and rate > 0:
            usd_amt, ars_amt = (amount, amount * rate) if is_usd else (amount / rate, amount)
        else:
            ars_amt = 0.0 if is_usd else amount
            usd_amt = amount if is_usd else 0.0

        if o.event_kind == "DIVIDENDO":
            div_ars += ars_amt
            div_usd += usd_amt
        elif o.event_kind == "RENTA":
            renta_ars += ars_amt
            renta_usd += usd_amt
        elif o.event_kind == "AMORTIZACION":
            amort_ars += ars_amt
            amort_usd += usd_amt

    return {
        "total_ars": round(total_ars, 2),
        "total_usd": round(total_usd, 2),
        "dolar_rate": round(dolar_rate, 4),
        "dolar_source": dolar_source,
        "pnl_no_realizada_ars": round(pnl_no_realizada_ars, 2),
        "pnl_no_realizada_usd": round(pnl_no_realizada_usd, 2),
        "dividendos_2026_ars": round(div_ars, 2),
        "dividendos_2026_usd": round(div_usd, 2),
        "renta_2026_ars": round(renta_ars, 2),
        "renta_2026_usd": round(renta_usd, 2),
        "amortizaciones_2026_ars": round(amort_ars, 2),
        "amortizaciones_2026_usd": round(amort_usd, 2),
        "n_operaciones_2026": n_ops_2026,
        "distribucion_por_clase": distribucion,
    }


def upcoming_events(db: Session, user_id: int) -> list[dict]:
    """Estimate upcoming RENTA/AMORTIZACION payments for held ONs and Bonos."""
    bond_classes = ("ON", "Bono", "Letra")
    holdings = (
        db.query(Holding)
        .filter(Holding.user_id == user_id, Holding.clase.in_(bond_classes))
        .all()
    )
    today = date.today()
    results = []
    for h in holdings:
        events = (
            db.query(Operation)
            .filter(
                Operation.user_id == user_id,
                Operation.simbolo == h.simbolo,
                Operation.event_kind.in_(["RENTA", "AMORTIZACION"]),
            )
            .order_by(Operation.fecha_operada.desc())
            .limit(5)
            .all()
        )
        if not events:
            # Fallback for zero-coupon / bullet bonds with no payment history.
            # Infer maturity year from ticker suffix (TZX26 → 2026, GD35 → 2035).
            from .ons_whitelist import normalize_ticker as _nt
            base, _ = _nt(h.simbolo)
            m = re.match(r'^[A-Z]+(\d{2})$', base)
            if m:
                bond_year = int(m.group(1)) + 2000
                if today.year <= bond_year <= today.year + 12:
                    maturity = date(bond_year, 6, 30)
                    if maturity > today:
                        moneda_low = (h.moneda or "").lower()
                        cur = "ARS" if ("peso" in moneda_low or moneda_low == "ars" or not moneda_low) else "USD_MEP"
                        estimated = _f(h.valuacion_ars) if cur == "ARS" else _f(h.valuacion_usd)
                        results.append({
                            "simbolo": h.simbolo,
                            "descripcion": h.descripcion or h.simbolo,
                            "clase": h.clase,
                            "event_kind": "AMORTIZACION",
                            "estimated_date": maturity.isoformat(),
                            "last_amount": round(estimated, 2),
                            "currency_kind": cur,
                            "interval_days": 0,
                        })
            continue

        last = events[0]
        if not last.fecha_operada:
            continue

        # Find two events with distinct dates (RENTA + AMORTIZACION can share a date)
        prev = next(
            (e for e in events[1:] if e.fecha_operada and e.fecha_operada != last.fecha_operada),
            None,
        )
        if prev and prev.fecha_operada:
            interval = abs((last.fecha_operada - prev.fecha_operada).days)
            interval = max(interval, 14)
        else:
            # ONs argentina: mayoría trimestral (90d), bonos soberanos semestral (180d)
            interval = 90 if h.clase == "ON" else 180

        # IOL registra devengamientos mensuales incluso para bonos bianuales/trimestrales.
        # Si el intervalo detectado es < 60d y tenemos 3+ eventos, son accruals → usar 180d.
        if interval < 60 and len(events) >= 3:
            interval = 180

        next_date = last.fecha_operada + timedelta(days=interval)
        while next_date <= today:
            next_date += timedelta(days=interval)

        last_amount_raw = abs(_f(last.monto_neto) if last.monto_neto is not None else _f(last.monto_operado))
        # Scale projected amount by current holding nominal vs nominal at last payment
        op_cantidad = _f(last.cantidad) if last.cantidad is not None else 0.0
        h_cantidad = _f(h.cantidad) if h.cantidad is not None else 0.0
        if op_cantidad > 0 and h_cantidad > 0:
            estimated_amount = (last_amount_raw / op_cantidad) * h_cantidad
        else:
            estimated_amount = last_amount_raw

        results.append({
            "simbolo": h.simbolo,
            "descripcion": h.descripcion or h.simbolo,
            "clase": h.clase,
            "event_kind": last.event_kind,
            "estimated_date": next_date.isoformat(),
            "last_amount": round(estimated_amount, 2),
            "currency_kind": last.currency_kind,
            "interval_days": interval,
        })

    results.sort(key=lambda x: x["estimated_date"])
    return results


def save_snapshot(
    db: Session,
    user_id: int,
    *,
    on_date: date | None = None,
    dolar_rate: float,
    dolar_source: str,
    source: str = "scheduler",
) -> PortfolioSnapshot:
    target = on_date or date.today()
    holdings = db.query(Holding).filter(
        Holding.user_id == user_id, Holding.clase != "Caucion"
    ).all()
    total_ars = sum(_f(h.valuacion_ars) for h in holdings)
    total_usd = sum(_f(h.valuacion_usd) for h in holdings)
    breakdown = [
        {
            "simbolo": h.simbolo,
            "clase": h.clase,
            "mercado": h.mercado,
            "cantidad": _f(h.cantidad),
            "ultimo_precio": _f(h.ultimo_precio),
            "valuacion_ars": _f(h.valuacion_ars),
            "valuacion_usd": _f(h.valuacion_usd),
        }
        for h in holdings
    ]
    row = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.user_id == user_id, PortfolioSnapshot.date == target)
        .first()
    )
    if row is None:
        row = PortfolioSnapshot(user_id=user_id, date=target)
        db.add(row)
    row.taken_at = datetime.now(tz=timezone.utc)
    row.total_ars = total_ars
    row.total_usd = total_usd
    row.dolar_rate = dolar_rate
    row.dolar_source = dolar_source
    row.breakdown_json = breakdown
    row.source = source
    db.commit()
    return row
