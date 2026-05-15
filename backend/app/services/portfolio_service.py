"""Portfolio service: refresh holdings from IOL + compute KPIs."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy.orm import Session

from ..models import Holding, Operation, PortfolioSnapshot
from . import dolar_service
from .classifier import classify_asset
from .iol_client import IolClient

log = logging.getLogger(__name__)


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
        "moneda": moneda,
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
    for mercado, pf in pais_data.items():
        for activo in _iter_titulos(pf):
            row_data = _extract_row(activo, mercado)
            if row_data is None:
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
            holding.moneda = row_data["moneda"]
            rows.append(holding)

    # Drop holdings no longer in IOL portfolio
    existing = db.query(Holding).filter(Holding.user_id == user_id).all()
    for h in existing:
        if (h.mercado, h.simbolo) not in keep_keys:
            db.delete(h)

    db.commit()
    return rows


def compute_kpis(db: Session, user_id: int, *, dolar_rate: float, dolar_source: str) -> dict:
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
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

    # P&L realizada / dividendos / renta del 2026 desde Operations
    ops = db.query(Operation).filter(Operation.user_id == user_id).all()
    pnl_realizada_2026_ars = 0.0
    pnl_realizada_2026_usd = 0.0
    div_ars = 0.0
    div_usd = 0.0
    renta_ars = 0.0
    renta_usd = 0.0
    n_ops_2026 = 0
    for o in ops:
        if not o.fecha_operada or o.fecha_operada.year != 2026:
            continue
        n_ops_2026 += 1
        amount = _f(o.monto_neto) if o.monto_neto is not None else _f(o.monto_operado)
        usd = o.currency_kind in ("USD_MEP", "USD_CABLE")
        if o.event_kind == "VENTA":
            if usd:
                pnl_realizada_2026_usd += amount
            else:
                pnl_realizada_2026_ars += amount
        elif o.event_kind == "COMPRA":
            if usd:
                pnl_realizada_2026_usd -= amount
            else:
                pnl_realizada_2026_ars -= amount
        elif o.event_kind == "DIVIDENDO":
            if usd:
                div_usd += amount
            else:
                div_ars += amount
        elif o.event_kind in ("RENTA", "AMORTIZACION"):
            if usd:
                renta_usd += amount
            else:
                renta_ars += amount

    return {
        "total_ars": round(total_ars, 2),
        "total_usd": round(total_usd, 2),
        "dolar_rate": round(dolar_rate, 4),
        "dolar_source": dolar_source,
        "pnl_no_realizada_ars": round(pnl_no_realizada_ars, 2),
        "pnl_realizada_2026_ars": round(pnl_realizada_2026_ars, 2),
        "pnl_realizada_2026_usd": round(pnl_realizada_2026_usd, 2),
        "dividendos_2026_ars": round(div_ars, 2),
        "dividendos_2026_usd": round(div_usd, 2),
        "renta_2026_ars": round(renta_ars, 2),
        "renta_2026_usd": round(renta_usd, 2),
        "n_operaciones_2026": n_ops_2026,
        "distribucion_por_clase": distribucion,
    }


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
    holdings = db.query(Holding).filter(Holding.user_id == user_id).all()
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
