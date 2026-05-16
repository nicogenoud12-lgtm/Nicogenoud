"""Aggregate crypto holdings + CoinGecko prices into a live report.

Prices come in USD; ARS is derived using the user's configured dolar source
(MEP by default) so values are comparable with the rest of the dashboard.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..crud import get_setting
from ..models import CryptoHolding, CryptoSnapshot, DolarQuote
from . import coingecko, dolar_service
from .coingecko import CoinGeckoError

log = logging.getLogger(__name__)

DEFAULT_BACKFILL_SINCE = date(2026, 1, 1)


async def _get_dolar_rate(db: Session) -> tuple[float, str]:
    source = get_setting(db, "dolar_source", "MEP") or "MEP"
    try:
        dq = await dolar_service.get_or_fetch(db, d=date.today(), source=source)
        rate = float(dq.promedio) if dq else 0.0
    except Exception:
        log.exception("crypto report: dolar fetch failed")
        rate = 0.0
    return rate, source


async def build_report(db: Session, user_id: int) -> dict:
    holdings: list[CryptoHolding] = (
        db.query(CryptoHolding)
        .filter(CryptoHolding.user_id == user_id)
        .order_by(CryptoHolding.symbol.asc(), CryptoHolding.id.asc())
        .all()
    )

    ids = [h.coingecko_id for h in holdings if h.coingecko_id]
    prices: dict[str, dict] = {}
    fetch_error: Optional[str] = None
    if ids:
        try:
            prices = await coingecko.get_prices(ids, vs_currencies=["usd"], include_24h_change=True)
        except CoinGeckoError as e:
            fetch_error = str(e)
            log.warning("crypto report: %s", e)

    ars_rate, dolar_src = await _get_dolar_rate(db)

    items: list[dict] = []
    total_value_usd = 0.0
    total_cost_usd = 0.0
    missing: list[str] = []

    for h in holdings:
        cant = float(h.cantidad or 0)
        cost_unit = float(h.costo_usd_unit) if h.costo_usd_unit is not None else None
        cost_total = (cost_unit * cant) if cost_unit is not None else None

        price_usd: Optional[float] = None
        change_24h: Optional[float] = None
        if h.coingecko_id:
            info = prices.get(h.coingecko_id.lower())
            if info:
                if info.get("usd") is not None:
                    price_usd = float(info["usd"])
                if info.get("usd_24h_change") is not None:
                    change_24h = float(info["usd_24h_change"])
        else:
            missing.append(h.symbol)

        value_usd = (price_usd * cant) if price_usd is not None else None
        value_ars = (value_usd * ars_rate) if (value_usd is not None and ars_rate) else None
        price_ars = (price_usd * ars_rate) if (price_usd is not None and ars_rate) else None
        pnl_usd = (
            (value_usd - cost_total)
            if (value_usd is not None and cost_total is not None)
            else None
        )
        pnl_pct = (pnl_usd / cost_total * 100) if (pnl_usd is not None and cost_total) else None

        if value_usd is not None:
            total_value_usd += value_usd
        if cost_total is not None:
            total_cost_usd += cost_total

        items.append(
            {
                "id": h.id,
                "symbol": h.symbol,
                "name": h.name,
                "coingecko_id": h.coingecko_id,
                "cantidad": cant,
                "costo_usd_unit": cost_unit,
                "costo_total_usd": cost_total,
                "price_usd": price_usd,
                "price_ars": price_ars,
                "value_usd": value_usd,
                "value_ars": value_ars,
                "pnl_usd": pnl_usd,
                "pnl_pct": pnl_pct,
                "change_24h_pct": change_24h,
                "exchange": h.exchange,
                "has_price": price_usd is not None,
                "pct_portfolio": 0.0,
            }
        )

    for it in items:
        if it["value_usd"] and total_value_usd:
            it["pct_portfolio"] = it["value_usd"] / total_value_usd * 100

    pnl_total_usd = total_value_usd - total_cost_usd
    pnl_total_pct = (pnl_total_usd / total_cost_usd * 100) if total_cost_usd else None
    total_value_ars = total_value_usd * ars_rate if ars_rate else 0.0

    return {
        "items": items,
        "total_value_usd": total_value_usd,
        "total_value_ars": total_value_ars,
        "total_cost_usd": total_cost_usd,
        "pnl_total_usd": pnl_total_usd,
        "pnl_total_pct": pnl_total_pct,
        "ars_rate": ars_rate or 0.0,
        "dolar_source": dolar_src,
        "fetched_at": datetime.now(tz=timezone.utc),
        "missing_coingecko": missing,
        "fetch_error": fetch_error,
    }


def upsert_snapshot(
    db: Session,
    *,
    user_id: int,
    on_date: date,
    total_usd: float,
    total_ars: float,
    cost_usd: float,
    dolar_rate: float,
    breakdown: list[dict],
) -> CryptoSnapshot:
    row = (
        db.query(CryptoSnapshot)
        .filter(CryptoSnapshot.user_id == user_id, CryptoSnapshot.date == on_date)
        .first()
    )
    if row is None:
        row = CryptoSnapshot(
            user_id=user_id,
            date=on_date,
            total_usd=total_usd,
            total_ars=total_ars,
            cost_usd=cost_usd,
            dolar_rate=dolar_rate,
            breakdown_json=breakdown,
        )
        db.add(row)
    else:
        row.total_usd = total_usd
        row.total_ars = total_ars
        row.cost_usd = cost_usd
        row.dolar_rate = dolar_rate
        row.breakdown_json = breakdown
        row.taken_at = datetime.now(tz=timezone.utc)
    db.commit()
    db.refresh(row)
    return row


async def build_report_and_snapshot(db: Session, user_id: int) -> dict:
    report = await build_report(db, user_id)
    if report["total_value_usd"] > 0:
        breakdown = [
            {
                "symbol": it["symbol"],
                "value_usd": it["value_usd"],
                "pct": it["pct_portfolio"],
            }
            for it in report["items"]
            if it["value_usd"]
        ]
        upsert_snapshot(
            db,
            user_id=user_id,
            on_date=date.today(),
            total_usd=report["total_value_usd"],
            total_ars=report["total_value_ars"],
            cost_usd=report["total_cost_usd"],
            dolar_rate=report["ars_rate"],
            breakdown=breakdown,
        )
    return report


def _nearest_price(history: dict[date, float], target: date) -> Optional[float]:
    """Return the price on `target`, or the most recent prior price if missing."""
    if not history:
        return None
    if target in history:
        return history[target]
    earlier = [d for d in history if d <= target]
    if not earlier:
        # Pick the earliest available (helps when target predates the coin's history)
        return history[min(history)]
    return history[max(earlier)]


async def backfill_history(
    db: Session,
    user_id: int,
    *,
    since: date = DEFAULT_BACKFILL_SINCE,
    until: Optional[date] = None,
) -> dict:
    """Compute daily snapshots from `since` to today using current holdings + historical prices.

    Assumes the user has held the *current* quantities since `since`. This is
    a backwards-looking simulation, not a true purchase-history reconstruction.
    """
    until = until or date.today()
    holdings: list[CryptoHolding] = (
        db.query(CryptoHolding).filter(CryptoHolding.user_id == user_id).all()
    )
    if not holdings:
        return {"days": 0, "since": since.isoformat(), "until": until.isoformat()}

    # Pull historical USD prices per coin
    histories: dict[str, dict[date, float]] = {}
    failed: list[str] = []
    for h in holdings:
        cid = (h.coingecko_id or "").strip().lower()
        if not cid:
            failed.append(h.symbol)
            continue
        try:
            histories[cid] = await coingecko.fetch_history_usd(cid, since, until)
        except CoinGeckoError as e:
            log.warning("backfill: history failed for %s (%s): %s", h.symbol, cid, e)
            failed.append(h.symbol)

    if not histories:
        return {
            "days": 0,
            "since": since.isoformat(),
            "until": until.isoformat(),
            "failed_symbols": failed,
        }

    # Historical ARS rate from DolarQuote table; fall back to most recent / current
    dolar_source = get_setting(db, "dolar_source", "MEP") or "MEP"
    quotes = (
        db.query(DolarQuote)
        .filter(DolarQuote.source == dolar_source, DolarQuote.date >= since)
        .order_by(DolarQuote.date.asc())
        .all()
    )
    rate_history = {dq.date: float(dq.promedio) for dq in quotes if dq.promedio}
    fallback_rate, _ = await _get_dolar_rate(db)

    # Cost is current total cost (constant across the simulated history)
    cost_usd = sum(
        float(h.costo_usd_unit or 0) * float(h.cantidad or 0)
        for h in holdings
        if h.costo_usd_unit is not None
    )

    days = 0
    cur = since
    while cur <= until:
        total_usd = 0.0
        breakdown: list[dict] = []
        for h in holdings:
            cid = (h.coingecko_id or "").strip().lower()
            if not cid:
                continue
            price = _nearest_price(histories.get(cid, {}), cur)
            if price is None:
                continue
            qty = float(h.cantidad or 0)
            value = qty * price
            total_usd += value
            if value:
                breakdown.append({"symbol": h.symbol, "value_usd": value})

        if total_usd > 0:
            rate = rate_history.get(cur)
            if rate is None:
                prior = [d for d in rate_history if d <= cur]
                rate = rate_history[max(prior)] if prior else fallback_rate

            upsert_snapshot(
                db,
                user_id=user_id,
                on_date=cur,
                total_usd=total_usd,
                total_ars=total_usd * (rate or 0),
                cost_usd=cost_usd,
                dolar_rate=rate or 0,
                breakdown=breakdown,
            )
            days += 1
        cur += timedelta(days=1)

    return {
        "days": days,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "failed_symbols": failed,
    }
