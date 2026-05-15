"""Aggregations of P&L from Operations, segregated by currency_kind."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from ..models import Operation


def _f(v) -> float:
    return float(v) if v is not None else 0.0


def operations_summary(db: Session, user_id: int, *, year: int) -> dict:
    desde = date(year, 1, 1)
    hasta = date(year, 12, 31)
    ops = (
        db.query(Operation)
        .filter(
            Operation.user_id == user_id,
            Operation.fecha_operada >= desde,
            Operation.fecha_operada <= hasta,
        )
        .all()
    )

    totals = {
        "total_compras_ars": 0.0,
        "total_ventas_ars": 0.0,
        "total_compras_usd": 0.0,
        "total_ventas_usd": 0.0,
        "total_dividendos_ars": 0.0,
        "total_dividendos_usd": 0.0,
        "total_renta_ars": 0.0,
        "total_renta_usd": 0.0,
    }
    by_simbolo: dict[str, dict] = defaultdict(
        lambda: {"compras_ars": 0.0, "ventas_ars": 0.0, "compras_usd": 0.0, "ventas_usd": 0.0, "n": 0}
    )
    by_mes: dict[int, dict] = defaultdict(
        lambda: {"compras": 0.0, "ventas": 0.0, "renta": 0.0, "dividendos": 0.0}
    )

    for o in ops:
        amount = _f(o.monto_neto) if o.monto_neto is not None else _f(o.monto_operado)
        usd = o.currency_kind in ("USD_MEP", "USD_CABLE")
        mes = o.fecha_operada.month if o.fecha_operada else 0
        sym = o.simbolo or "(s/d)"
        by_simbolo[sym]["n"] += 1

        if o.event_kind == "COMPRA":
            if usd:
                totals["total_compras_usd"] += amount
                by_simbolo[sym]["compras_usd"] += amount
            else:
                totals["total_compras_ars"] += amount
                by_simbolo[sym]["compras_ars"] += amount
            by_mes[mes]["compras"] += amount
        elif o.event_kind == "VENTA":
            if usd:
                totals["total_ventas_usd"] += amount
                by_simbolo[sym]["ventas_usd"] += amount
            else:
                totals["total_ventas_ars"] += amount
                by_simbolo[sym]["ventas_ars"] += amount
            by_mes[mes]["ventas"] += amount
        elif o.event_kind == "DIVIDENDO":
            if usd:
                totals["total_dividendos_usd"] += amount
            else:
                totals["total_dividendos_ars"] += amount
            by_mes[mes]["dividendos"] += amount
        elif o.event_kind in ("RENTA", "AMORTIZACION"):
            if usd:
                totals["total_renta_usd"] += amount
            else:
                totals["total_renta_ars"] += amount
            by_mes[mes]["renta"] += amount

    by_simbolo_list = [
        {"simbolo": k, **{kk: round(vv, 2) if isinstance(vv, float) else vv for kk, vv in v.items()}}
        for k, v in sorted(by_simbolo.items(), key=lambda kv: kv[0])
    ]
    by_mes_list = [
        {
            "mes": m,
            **{k: round(v, 2) for k, v in by_mes[m].items()},
        }
        for m in sorted(by_mes.keys())
    ]

    return {
        "year": year,
        "count": len(ops),
        **{k: round(v, 2) for k, v in totals.items()},
        "by_simbolo": by_simbolo_list,
        "by_mes": by_mes_list,
    }
