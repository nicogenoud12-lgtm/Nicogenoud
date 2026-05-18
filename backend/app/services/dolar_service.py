"""Dolar quotes via dolarapi.com — tolerant parser, daily upsert.

Historical MEP backfill uses api.argentinadatos.com which has the full series.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import DolarQuote

log = logging.getLogger(__name__)

ARGENTINADATOS_BASE = "https://api.argentinadatos.com/v1"


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


async def backfill_historical_mep(db: Session, desde: date, hasta: date) -> int:
    """Fetch full MEP series from ArgentinaDatos and upsert rows in DolarQuote.

    Idempotent — skips dates already in DB. Returns number of new rows inserted.
    Logs a WARNING and returns 0 if the external endpoint is unreachable.
    """
    try:
        async with httpx.AsyncClient(timeout=20) as cli:
            r = await cli.get(f"{ARGENTINADATOS_BASE}/cotizaciones/dolares/bolsa")
            r.raise_for_status()
            rows = r.json()
    except Exception as e:
        log.warning("backfill_historical_mep: ArgentinaDatos request failed: %s", e)
        return 0

    existing = {
        d_
        for (d_,) in db.query(DolarQuote.date).filter(
            DolarQuote.source == "MEP",
            DolarQuote.date >= desde,
            DolarQuote.date <= hasta,
        ).all()
    }

    inserted = 0
    for row in rows:
        try:
            f = date.fromisoformat(str(row.get("fecha", ""))[:10])
        except ValueError:
            continue
        if f < desde or f > hasta or f in existing:
            continue
        compra = _to_float(row.get("compra"))
        venta = _to_float(row.get("venta"))
        promedio = _avg(compra, venta) or compra or venta or 0.0
        if not promedio:
            continue
        db.add(DolarQuote(date=f, source="MEP", compra=compra, venta=venta, promedio=promedio))
        inserted += 1

    if inserted:
        db.commit()
    log.info("backfill_historical_mep: inserted %d rows (desde=%s hasta=%s)", inserted, desde, hasta)
    return inserted


def build_mep_lookup(db: Session, desde: date, hasta: date) -> dict[date, float]:
    """Return {date → promedio} for MEP rates covering desde-30d to hasta+30d.

    Used by pnl.py and portfolio_service.py to convert amounts at historical rates.
    """
    from datetime import timedelta
    quotes = (
        db.query(DolarQuote)
        .filter(
            DolarQuote.source == "MEP",
            DolarQuote.date >= desde - timedelta(days=30),
            DolarQuote.date <= hasta + timedelta(days=30),
        )
        .order_by(DolarQuote.date)
        .all()
    )
    return {q.date: float(q.promedio or q.venta or q.compra or 0) for q in quotes if (q.promedio or q.venta or q.compra)}


def fx_for_date(mep_lookup: dict[date, float], sorted_dates: list[date], target: date) -> Optional[float]:
    """Return MEP rate for target date with nearest-date fallback."""
    v = mep_lookup.get(target)
    if v:
        return v
    prev = next((x for x in reversed(sorted_dates) if x < target), None)
    if prev:
        return mep_lookup[prev]
    nxt = next((x for x in sorted_dates if x > target), None)
    return mep_lookup[nxt] if nxt else None


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
