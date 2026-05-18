"""Aggregations of P&L from Operations.

All monetary totals are expressed in BOTH ARS and USD using the MEP rate of
each operation's fecha_operada, so the frontend can show a single unified
total in whichever currency the user toggles.

Conversion rules (by explicit user decision):
  - USD_MEP / USD_CABLE operations: amount_usd = monto_neto; amount_ars = amount_usd × MEP
  - ARS operations:                 amount_ars = monto_neto; amount_usd = amount_ars ÷ MEP
  - No MEP for that date: amount is counted only in its native currency (no artificial inflation).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..models import DolarQuote, Operation
from .dolar_service import build_mep_lookup, fx_for_date


def _f(v) -> float:
    return float(v) if v is not None else 0.0


_BUCKETS = {
    "COMPRA":       ("total_compras_ars",    "total_compras_usd"),
    "VENTA":        ("total_ventas_ars",     "total_ventas_usd"),
    "DIVIDENDO":    ("total_dividendos_ars", "total_dividendos_usd"),
    "RENTA":        ("total_renta_ars",      "total_renta_usd"),
    "AMORTIZACION": ("total_renta_ars",      "total_renta_usd"),
}


def operations_summary(db: Session, user_id: int, *, from_date: date, to_date: date) -> dict:
    ops = (
        db.query(Operation)
        .filter(
            Operation.user_id == user_id,
            Operation.fecha_operada >= from_date,
            Operation.fecha_operada <= to_date,
        )
        .all()
    )

    mep = build_mep_lookup(db, from_date, to_date)
    sorted_dates = sorted(mep.keys())

    def fx(d: Optional[date]) -> Optional[float]:
        if not d:
            return None
        return fx_for_date(mep, sorted_dates, d)

    totals: dict[str, float] = {
        "total_compras_ars": 0.0,    "total_compras_usd": 0.0,
        "total_ventas_ars": 0.0,     "total_ventas_usd": 0.0,
        "total_renta_ars": 0.0,      "total_renta_usd": 0.0,
        "total_dividendos_ars": 0.0, "total_dividendos_usd": 0.0,
    }
    missing_fx = 0
    by_simbolo: dict[str, dict] = defaultdict(
        lambda: {"compras_ars": 0.0, "ventas_ars": 0.0,
                 "compras_usd": 0.0, "ventas_usd": 0.0, "n": 0}
    )
    by_mes: dict[int, dict] = defaultdict(
        lambda: {"compras_ars": 0.0, "ventas_ars": 0.0,
                 "compras_usd": 0.0, "ventas_usd": 0.0,
                 "renta_ars": 0.0, "renta_usd": 0.0,
                 "dividendos_ars": 0.0, "dividendos_usd": 0.0}
    )

    for o in ops:
        amount = abs(_f(o.monto_neto) if o.monto_neto is not None else _f(o.monto_operado))
        is_usd = o.currency_kind in ("USD_MEP", "USD_CABLE")
        rate = fx(o.fecha_operada)

        if rate is None or rate <= 0:
            missing_fx += 1
            ars = 0.0 if is_usd else amount
            usd = amount if is_usd else 0.0
        else:
            if is_usd:
                usd, ars = amount, amount * rate
            else:
                ars, usd = amount, amount / rate

        bucket = _BUCKETS.get(o.event_kind)
        if bucket:
            totals[bucket[0]] += ars
            totals[bucket[1]] += usd

        sym = o.simbolo or "(s/d)"
        mes = o.fecha_operada.month if o.fecha_operada else 0
        by_simbolo[sym]["n"] += 1

        if o.event_kind == "COMPRA":
            by_simbolo[sym]["compras_ars"] += ars
            by_simbolo[sym]["compras_usd"] += usd
            by_mes[mes]["compras_ars"] += ars
            by_mes[mes]["compras_usd"] += usd
        elif o.event_kind == "VENTA":
            by_simbolo[sym]["ventas_ars"] += ars
            by_simbolo[sym]["ventas_usd"] += usd
            by_mes[mes]["ventas_ars"] += ars
            by_mes[mes]["ventas_usd"] += usd
        elif o.event_kind in ("RENTA", "AMORTIZACION"):
            by_mes[mes]["renta_ars"] += ars
            by_mes[mes]["renta_usd"] += usd
        elif o.event_kind == "DIVIDENDO":
            by_mes[mes]["dividendos_ars"] += ars
            by_mes[mes]["dividendos_usd"] += usd

    by_simbolo_list = [
        {"simbolo": k, **{kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()}}
        for k, v in sorted(by_simbolo.items())
    ]
    by_mes_list = [
        {"mes": m, **{k: round(v, 2) for k, v in by_mes[m].items()}}
        for m in sorted(by_mes.keys())
    ]

    return {
        "year": from_date.year,
        "from_date": from_date,
        "to_date": to_date,
        "count": len(ops),
        **{k: round(v, 2) for k, v in totals.items()},
        "fx_source": "MEP",
        "fx_missing_count": missing_fx,
        "by_simbolo": by_simbolo_list,
        "by_mes": by_mes_list,
    }
