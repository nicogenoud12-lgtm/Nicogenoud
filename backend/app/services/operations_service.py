"""Operations sync from IOL — idempotent upsert by (user_id, iol_numero)."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from ..models import Operation
from .classifier import classify_asset, classify_event
from .iol_client import IolClient

log = logging.getLogger(__name__)


def _parse_date(v: Any) -> date | None:
    if not v:
        return None
    if isinstance(v, date):
        return v
    s = str(v)
    # IOL puede devolver "2026-01-15T00:00:00" o "2026-01-15"
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _str(v) -> str | None:
    return None if v is None else str(v)


async def sync_operations(
    db: Session,
    user_id: int,
    *,
    year: int,
    hasta: date | None = None,
) -> int:
    """Pull /operaciones for the given year, upsert by iol_numero. Returns # rows touched."""
    desde = date(year, 1, 1)
    hasta = hasta or date.today()
    async with IolClient(db, user_id) as client:
        ops = await client.get_operaciones(estado="terminadas", desde=desde, hasta=hasta)

    log.info("sync_operations: IOL returned %d raw rows (user=%d, year=%d)", len(ops), user_id, year)

    touched = 0
    skipped_no_numero = 0
    for raw in ops:
        if not isinstance(raw, dict):
            continue
        numero = (
            raw.get("numero")
            or raw.get("Numero")
            or raw.get("numeroOperacion")
            or raw.get("numeroOrden")
            or raw.get("id")
        )
        if numero is None:
            skipped_no_numero += 1
            if skipped_no_numero <= 3:
                log.warning("sync_operations: row without numero: keys=%s", list(raw.keys()))
            continue
        iol_numero = str(numero)

        simbolo = raw.get("simbolo") or raw.get("Simbolo")
        descripcion = raw.get("descripcion") or raw.get("Descripcion")
        tipo = raw.get("tipo") or raw.get("Tipo")
        moneda = raw.get("moneda") or raw.get("Moneda")
        mercado = raw.get("mercado") or raw.get("Mercado")
        estado = raw.get("estado") or raw.get("Estado")

        asset_class = classify_asset(
            simbolo=simbolo, tipo=None, descripcion=descripcion, mercado=mercado
        )
        event_kind, currency_kind = classify_event(
            tipo=tipo,
            descripcion=descripcion,
            simbolo=simbolo,
            moneda=moneda,
            asset_class=asset_class,
        )

        op = (
            db.query(Operation)
            .filter(Operation.user_id == user_id, Operation.iol_numero == iol_numero)
            .first()
        )
        if op is None:
            op = Operation(user_id=user_id, iol_numero=iol_numero)
            db.add(op)

        op.fecha_operada = _parse_date(raw.get("fechaOperada") or raw.get("fechaOrden") or raw.get("fecha"))
        op.fecha_liquidacion = _parse_date(raw.get("fechaLiquidacion"))
        op.tipo = _str(tipo)
        op.event_kind = event_kind
        op.currency_kind = currency_kind
        op.estado = _str(estado)
        op.simbolo = _str(simbolo)
        op.descripcion = _str(descripcion)[:255] if descripcion else None
        op.mercado = _str(mercado)
        op.cantidad = _f(raw.get("cantidad") or raw.get("cantidadOperada"))
        op.precio = _f(raw.get("precioOperado") or raw.get("precio"))
        op.monto_operado = _f(raw.get("montoOperado") or raw.get("monto"))
        op.comisiones = _f(raw.get("comision") or raw.get("comisiones"))
        op.derechos_mercado = _f(raw.get("derechosMercado"))
        op.iva = _f(raw.get("iva"))
        op.monto_neto = _f(raw.get("monto") or raw.get("netoOperado") or raw.get("montoNeto"))
        op.moneda = _str(moneda)
        op.raw_json = raw
        touched += 1

    db.commit()
    log.info(
        "sync_operations: upserted=%d skipped_no_numero=%d user=%d year=%d",
        touched, skipped_no_numero, user_id, year,
    )
    return touched
