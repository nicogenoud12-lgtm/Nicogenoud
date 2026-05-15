"""Dolar quotes via dolarapi.com — tolerant parser, daily upsert."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import DolarQuote

log = logging.getLogger(__name__)


# dolarapi.com endpoint paths
_PATHS = {
    "MEP": "/dolares/bolsa",
    "CCL": "/dolares/contadoconliqui",
    "Blue": "/dolares/blue",
    "Oficial": "/dolares/oficial",
}

SUPPORTED_SOURCES = list(_PATHS.keys())


def _path_for(source: str) -> str:
    if source not in _PATHS:
        raise ValueError(f"Unsupported dolar source: {source}")
    return _PATHS[source]


async def fetch_dolar(source: str) -> dict:
    """Returns dict with compra, venta, promedio."""
    path = _path_for(source)
    url = settings.dolarapi_base.rstrip("/") + path
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(url)
    r.raise_for_status()
    data = r.json()
    compra = _to_float(data.get("compra"))
    venta = _to_float(data.get("venta"))
    promedio = _avg(compra, venta) or _to_float(data.get("promedio")) or 0.0
    return {"compra": compra, "venta": venta, "promedio": promedio, "raw": data}


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _avg(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return (a + b) / 2.0


def upsert_quote(db: Session, *, d: date, source: str, compra, venta, promedio) -> DolarQuote:
    row = (
        db.query(DolarQuote)
        .filter(DolarQuote.date == d, DolarQuote.source == source)
        .first()
    )
    if row is None:
        row = DolarQuote(date=d, source=source, compra=compra, venta=venta, promedio=promedio)
        db.add(row)
    else:
        row.compra = compra
        row.venta = venta
        row.promedio = promedio
        row.fetched_at = datetime.now(tz=timezone.utc)
    db.commit()
    return row


async def get_or_fetch(db: Session, *, d: date, source: str) -> DolarQuote:
    row = (
        db.query(DolarQuote)
        .filter(DolarQuote.date == d, DolarQuote.source == source)
        .first()
    )
    if row is not None and row.promedio:
        return row
    data = await fetch_dolar(source)
    return upsert_quote(
        db,
        d=d,
        source=source,
        compra=data["compra"],
        venta=data["venta"],
        promedio=data["promedio"],
    )


async def fetch_all(db: Session, *, d: date | None = None) -> list[DolarQuote]:
    target_date = d or date.today()
    rows: list[DolarQuote] = []
    for source in SUPPORTED_SOURCES:
        try:
            data = await fetch_dolar(source)
            row = upsert_quote(
                db,
                d=target_date,
                source=source,
                compra=data["compra"],
                venta=data["venta"],
                promedio=data["promedio"],
            )
            rows.append(row)
        except Exception as e:
            log.warning("dolar fetch failed source=%s: %s", source, e)
    return rows
