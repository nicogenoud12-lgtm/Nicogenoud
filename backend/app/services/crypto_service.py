"""Aggregate crypto holdings + CoinGecko prices into a live report.

Prices come in USD; ARS is derived using the user's configured dolar source
(MEP by default) so values are comparable with the rest of the dashboard.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..crud import get_setting
from ..models import CryptoHolding, CryptoSale, CryptoSnapshot, DolarQuote
from . import binance as binance_svc
from . import coingecko, dolar_service
from .binance import BinanceError
from .coingecko import CoinGeckoError

log = logging.getLogger(__name__)

DEFAULT_BACKFILL_SINCE = date(2026, 1, 1)


def _resolve_missing_ids(db: Session, holdings: list[CryptoHolding]) -> int:
    """For each holding without a coingecko_id, try the well-known symbol map
    and persist any resolution so future fetches (live + history) work.
    Returns the number of holdings updated.
    """
    updated = 0
    for h in holdings:
        if (h.coingecko_id or "").strip():
            continue
        resolved = coingecko.resolve_id(h.symbol)
        if resolved:
            h.coingecko_id = resolved
            updated += 1
            log.info("crypto: auto-resolved coingecko_id=%s for symbol=%s", resolved, h.symbol)
    if updated:
        db.commit()
    return updated


async def _get_dolar_rate(db: Session) -> tuple[float, str]:
    source = get_setting(db, "dolar_source", "MEP") or "MEP"
    try:
        dq = await dolar_service.get_or_fetch(db, d=date.today(), source=source)
        rate = float(dq.promedio) if dq else 0.0
    except Exception:
        log.exception("crypto report: dolar fetch failed")
        rate = 0.0
    return rate, source


# Por debajo de esta cantidad consideramos la tenencia liquidada (evita restos
# por error de redondeo flotante al vender el total).
QTY_EPSILON = 1e-9


async def _get_live_price_usd(coingecko_id: str) -> Optional[float]:
    """Precio USD en vivo de un solo coin: Binance primero, CoinGecko fallback."""
    cid = (coingecko_id or "").strip().lower()
    if not cid:
        return None
    try:
        prices = await binance_svc.get_prices([cid])
        info = prices.get(cid)
        if info and info.get("usd") is not None:
            return float(info["usd"])
    except BinanceError as e:
        log.warning("crypto sell: Binance price failed for %s: %s", cid, e)
    try:
        cg = await coingecko.get_prices([cid], vs_currencies=["usd"], include_24h_change=False)
        info = cg.get(cid)
        if info and info.get("usd") is not None:
            return float(info["usd"])
    except CoinGeckoError as e:
        log.warning("crypto sell: CoinGecko price failed for %s: %s", cid, e)
    return None


async def sell_holding(
    db: Session,
    user_id: int,
    holding_id: int,
    *,
    cantidad: float,
    price_usd: Optional[float] = None,
    notas: Optional[str] = None,
) -> tuple[Optional[str], Optional[CryptoSale]]:
    """Vende (parcial o totalmente) una tenencia crypto.

    Calcula el P&L realizado contra el costo promedio (`costo_usd_unit`) de la
    tenencia previa, registra un `CryptoSale` y reduce la cantidad (manteniendo
    el costo promedio). Si la cantidad llega a ~0 elimina la tenencia.

    Devuelve `(error, sale)`: si `error` no es None, no se aplicó nada.
    """
    holding = (
        db.query(CryptoHolding)
        .filter(CryptoHolding.id == holding_id, CryptoHolding.user_id == user_id)
        .first()
    )
    if holding is None:
        return "Holding not found", None

    qty_held = float(holding.cantidad or 0)
    qty_sold = float(cantidad)
    if qty_sold <= 0:
        return "La cantidad a vender debe ser mayor a 0", None
    if qty_sold > qty_held + QTY_EPSILON:
        return (
            f"No podés vender {qty_sold} {holding.symbol}: sólo tenés {qty_held}",
            None,
        )

    # Precio de venta: el provisto o el precio en vivo.
    sale_price = float(price_usd) if price_usd is not None else None
    if sale_price is None:
        sale_price = await _get_live_price_usd(holding.coingecko_id or "")
    if sale_price is None:
        return (
            "No se pudo obtener un precio de venta. Ingresá el precio manualmente.",
            None,
        )

    cost_unit = float(holding.costo_usd_unit) if holding.costo_usd_unit is not None else None
    cost_total = (cost_unit * qty_sold) if cost_unit is not None else None
    proceeds = sale_price * qty_sold
    pnl = (proceeds - cost_total) if cost_total is not None else None
    pnl_pct = (pnl / cost_total * 100) if (pnl is not None and cost_total) else None

    ars_rate, _src = await _get_dolar_rate(db)

    sale = CryptoSale(
        user_id=user_id,
        symbol=holding.symbol,
        name=holding.name,
        coingecko_id=holding.coingecko_id,
        cantidad=qty_sold,
        costo_usd_unit=cost_unit,
        price_usd=sale_price,
        proceeds_usd=proceeds,
        cost_total_usd=cost_total,
        pnl_usd=pnl,
        pnl_pct=pnl_pct,
        dolar_rate=ars_rate or 0,
        notas=(notas or None) and notas.strip(),
    )
    db.add(sale)

    remaining = qty_held - qty_sold
    if remaining <= QTY_EPSILON:
        db.delete(holding)
    else:
        # Costo promedio se mantiene; sólo baja la cantidad.
        holding.cantidad = remaining

    db.commit()
    db.refresh(sale)
    return None, sale


def sales_report(db: Session, user_id: int, ars_rate: float, dolar_source: str) -> dict:
    sales: list[CryptoSale] = (
        db.query(CryptoSale)
        .filter(CryptoSale.user_id == user_id)
        .order_by(CryptoSale.sold_at.desc(), CryptoSale.id.desc())
        .all()
    )
    total_proceeds = sum(float(s.proceeds_usd or 0) for s in sales)
    total_cost = sum(float(s.cost_total_usd or 0) for s in sales if s.cost_total_usd is not None)
    total_pnl = sum(float(s.pnl_usd or 0) for s in sales if s.pnl_usd is not None)
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else None
    # P&L realizado en ARS: cada venta se convierte con SU cotización del día
    # de la venta (no la de hoy). Si una venta vieja no tiene cotización
    # guardada, se usa la actual como último recurso.
    total_pnl_ars = sum(
        float(s.pnl_usd) * (float(s.dolar_rate or 0) or (ars_rate or 0.0))
        for s in sales
        if s.pnl_usd is not None
    )
    return {
        "items": sales,
        "total_proceeds_usd": total_proceeds,
        "total_cost_usd": total_cost,
        "total_pnl_usd": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "total_pnl_ars": total_pnl_ars,
        "ars_rate": ars_rate or 0.0,
        "dolar_source": dolar_source,
    }


async def build_report(db: Session, user_id: int) -> dict:
    holdings: list[CryptoHolding] = (
        db.query(CryptoHolding)
        .filter(CryptoHolding.user_id == user_id)
        .order_by(CryptoHolding.symbol.asc(), CryptoHolding.id.asc())
        .all()
    )

    _resolve_missing_ids(db, holdings)

    ids = [h.coingecko_id for h in holdings if h.coingecko_id]
    prices: dict[str, dict] = {}
    fetch_error: Optional[str] = None
    if ids:
        # Binance first (1200 req/min, no key needed). CoinGecko fills any
        # gaps for coins without a Binance USDT pair.
        try:
            prices = await binance_svc.get_prices(ids)
            log.info("crypto report: Binance returned prices for %d/%d coins", len(prices), len(ids))
        except BinanceError as e:
            log.warning("crypto report: Binance failed (%s) — trying CoinGecko", e)

        missing = [cid for cid in ids if cid.lower() not in prices]
        if missing:
            try:
                cg_prices = await coingecko.get_prices(missing, vs_currencies=["usd"], include_24h_change=True)
                prices.update(cg_prices)
                log.info("crypto report: CoinGecko filled %d missing coins", len(cg_prices))
            except CoinGeckoError as e:
                if not prices:
                    fetch_error = str(e)
                log.warning("crypto report: CoinGecko gap-fill failed: %s", e)

        # 7d change is computed from Binance daily klines (parallel requests).
        try:
            changes_7d = await binance_svc.get_7d_changes(ids)
        except Exception as e:
            log.warning("crypto report: 7d change fetch failed: %s", e)
            changes_7d = {}
    else:
        changes_7d = {}

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
        change_7d: Optional[float] = None
        if h.coingecko_id:
            cid_lower = h.coingecko_id.lower()
            info = prices.get(cid_lower)
            if info:
                if info.get("usd") is not None:
                    price_usd = float(info["usd"])
                if info.get("usd_24h_change") is not None:
                    change_24h = float(info["usd_24h_change"])
            if cid_lower in changes_7d:
                change_7d = float(changes_7d[cid_lower])
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

        # El costo sólo suma si hay precio: si no, el P&L total cuenta como
        # pérdida el costo de monedas que no pudimos valuar.
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
                "change_7d_pct": change_7d,
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


def _report_is_complete(report: dict) -> bool:
    """True si todas las tenencias con fuente de precio (coingecko_id) tienen
    precio en este reporte. Las que no tienen ID nunca se valúan, así que no
    cuentan como faltantes."""
    return all(
        it["has_price"] for it in report["items"] if (it.get("coingecko_id") or "").strip()
    )


async def build_report_and_snapshot(db: Session, user_id: int) -> dict:
    report = await build_report(db, user_id)
    if report["total_value_usd"] > 0 and not _report_is_complete(report):
        # Falla parcial de precios (ej. Binance/CoinGecko no devolvió una
        # moneda): el total sale subvaluado. No pisamos el snapshot de hoy
        # para conservar el último bueno.
        faltan = [
            it["symbol"]
            for it in report["items"]
            if (it.get("coingecko_id") or "").strip() and not it["has_price"]
        ]
        log.warning(
            "crypto snapshot: sin precio para %s — no se actualiza el snapshot de hoy",
            ", ".join(faltan),
        )
    elif report["total_value_usd"] > 0:
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


def _sale_local_date(sold_at: datetime) -> date:
    """Fecha local de una venta. `sold_at` se guarda en UTC (SQLite lo devuelve
    naive); los snapshots usan `date.today()` en la zona del servidor (TZ del
    contenedor), así que convertimos a esa misma zona para comparar."""
    if sold_at.tzinfo is None:
        sold_at = sold_at.replace(tzinfo=timezone.utc)
    return sold_at.astimezone().date()


async def backfill_history(
    db: Session,
    user_id: int,
    *,
    since: date = DEFAULT_BACKFILL_SINCE,
    until: Optional[date] = None,
) -> dict:
    """Completa snapshots diarios faltantes entre `since` y `until` (hoy por
    defecto) con precios históricos.

    - Nunca pisa un snapshot existente: sólo crea los días que no tienen uno.
    - Cantidad por día: para cada símbolo, cantidad actual + lo vendido después
      de ese día (según `crypto_sales`), incluyendo monedas vendidas del todo
      (sin fila en `crypto_holdings`).
    - Costo por día: costo actual + costo base (`cost_total_usd`) de las ventas
      posteriores. Igual que el reporte en vivo, sólo cuenta el costo conocido.

    Aproximación: las compras no se registran con fecha (se fusionan en la
    tenencia), así que se asume que todo lo comprado ya se tenía desde `since`.
    """
    until = until or date.today()
    empty = {
        "days": 0,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "failed_symbols": [],
        "skipped_existing": 0,
        "skipped_incomplete": 0,
    }
    holdings: list[CryptoHolding] = (
        db.query(CryptoHolding).filter(CryptoHolding.user_id == user_id).all()
    )
    sales: list[CryptoSale] = (
        db.query(CryptoSale).filter(CryptoSale.user_id == user_id).all()
    )
    if not holdings and not sales:
        return empty

    resolved_count = _resolve_missing_ids(db, holdings)
    if resolved_count:
        log.info("backfill: auto-resolved coingecko_id for %d holdings", resolved_count)

    # Posiciones por símbolo: cantidad/costo actuales + ventas (fecha, qty, costo).
    positions: dict[str, dict] = {}

    def _pos(symbol: str) -> dict:
        key = (symbol or "").strip().upper()
        return positions.setdefault(
            key, {"symbol": key, "cid": None, "qty": 0.0, "cost": 0.0, "sales": []}
        )

    for h in holdings:
        p = _pos(h.symbol)
        p["qty"] += float(h.cantidad or 0)
        if h.costo_usd_unit is not None:
            p["cost"] += float(h.costo_usd_unit) * float(h.cantidad or 0)
        if (h.coingecko_id or "").strip():
            p["cid"] = h.coingecko_id.strip().lower()
    for sale in sales:
        p = _pos(sale.symbol)
        if not p["cid"] and (sale.coingecko_id or "").strip():
            p["cid"] = sale.coingecko_id.strip().lower()
        p["sales"].append(
            (
                _sale_local_date(sale.sold_at),
                float(sale.cantidad or 0),
                float(sale.cost_total_usd) if sale.cost_total_usd is not None else 0.0,
            )
        )
    for p in positions.values():
        if not p["cid"]:
            p["cid"] = coingecko.resolve_id(p["symbol"])

    def qty_on(p: dict, d: date) -> float:
        return p["qty"] + sum(q for sd, q, _c in p["sales"] if sd > d)

    def cost_on(p: dict, d: date) -> float:
        return p["cost"] + sum(c for sd, _q, c in p["sales"] if sd > d)

    existing = {
        d
        for (d,) in db.query(CryptoSnapshot.date)
        .filter(
            CryptoSnapshot.user_id == user_id,
            CryptoSnapshot.date >= since,
            CryptoSnapshot.date <= until,
        )
        .all()
    }
    dates_to_fill: list[date] = []
    cur = since
    while cur <= until:
        if cur not in existing:
            dates_to_fill.append(cur)
        cur += timedelta(days=1)
    if not dates_to_fill:
        return {**empty, "skipped_existing": len(existing)}

    # Sólo pedimos historia de las monedas que se tenían en algún día a completar.
    first_day = dates_to_fill[0]
    needed = [
        p for p in positions.values()
        if p["qty"] > QTY_EPSILON or any(sd > first_day for sd, _q, _c in p["sales"])
    ]

    # Pull historical USD prices per coin — Binance first (1200 req/min),
    # CoinGecko fallback for coins without a Binance USDT pair.
    histories: dict[str, dict[date, float]] = {}
    failed: list[str] = []
    for p in needed:
        cid = p["cid"]
        if not cid:
            failed.append(p["symbol"])
            continue
        if cid in histories:
            continue
        # Try Binance first
        try:
            data = await binance_svc.fetch_history_usd(cid, since, until)
            if data:
                histories[cid] = data
                log.info("backfill: Binance OK for %s (%d days)", p["symbol"], len(data))
                continue
        except BinanceError as e:
            log.warning("backfill: Binance failed for %s: %s — trying CoinGecko", p["symbol"], e)
        # CoinGecko fallback (with delay to respect free-tier rate limit)
        await asyncio.sleep(2)
        try:
            data = await coingecko.fetch_history_usd(cid, since, until)
            if data:
                histories[cid] = data
                log.info("backfill: CoinGecko fallback OK for %s (%d days)", p["symbol"], len(data))
            else:
                log.warning("backfill: CoinGecko returned empty for %s", p["symbol"])
                failed.append(p["symbol"])
        except CoinGeckoError as e2:
            log.warning("backfill: CoinGecko fallback failed for %s: %s", p["symbol"], e2)
            failed.append(p["symbol"])

    if not histories:
        return {
            **empty,
            "failed_symbols": failed,
            "skipped_existing": len(existing),
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

    days = 0
    skipped_incomplete = 0
    for cur in dates_to_fill:
        total_usd = 0.0
        cost_usd = 0.0
        breakdown: list[dict] = []
        incomplete = False
        for p in needed:
            qty = qty_on(p, cur)
            if qty <= QTY_EPSILON:
                continue
            cid = p["cid"]
            if not cid:
                # Sin fuente de precio: tampoco se valúa en el reporte en vivo.
                continue
            price = _nearest_price(histories.get(cid, {}), cur)
            if price is None:
                # Falta el precio de una moneda que se tenía ese día: el total
                # saldría subvaluado y, como después no se pisa, quedaría mal
                # para siempre. Mejor no crear el snapshot.
                incomplete = True
                break
            value = qty * price
            total_usd += value
            cost_usd += cost_on(p, cur)
            if value:
                breakdown.append({"symbol": p["symbol"], "value_usd": value})

        if incomplete:
            skipped_incomplete += 1
            continue
        if total_usd <= 0:
            continue
        for b in breakdown:
            b["pct"] = b["value_usd"] / total_usd * 100

        rate = rate_history.get(cur)
        if rate is None:
            prior = [d for d in rate_history if d <= cur]
            rate = rate_history[max(prior)] if prior else fallback_rate

        # Re-chequeo por si el reporte en vivo creó el de hoy mientras tanto.
        exists = (
            db.query(CryptoSnapshot.id)
            .filter(CryptoSnapshot.user_id == user_id, CryptoSnapshot.date == cur)
            .first()
        )
        if exists is not None:
            continue
        db.add(
            CryptoSnapshot(
                user_id=user_id,
                date=cur,
                total_usd=total_usd,
                total_ars=total_usd * (rate or 0),
                cost_usd=cost_usd,
                dolar_rate=rate or 0,
                breakdown_json=breakdown,
            )
        )
        db.commit()
        days += 1

    return {
        "days": days,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "failed_symbols": failed,
        "skipped_existing": len(existing),
        "skipped_incomplete": skipped_incomplete,
    }


def snapshots_with_flows(db: Session, user_id: int, since: date) -> list[dict]:
    """Snapshots desde `since` con el flujo neto de dinero de cada día.

    `flujo_usd` = plata que entró (+) / salió (-) del portfolio crypto entre el
    snapshot anterior de la lista (exclusive) y este (inclusive), para que el
    gráfico pueda separar rendimiento de aportes/retiros:
    variación = (valor - valor_prev - flujo) / valor_prev.

    Se deriva del costo: una compra sube el costo por lo invertido; una venta
    baja el costo por su base mientras el valor cae por lo cobrado
    (= base + P&L realizado). Entonces
        flujo = (costo_hoy - costo_prev) - P&L realizado de las ventas del tramo.
    Si una venta no tiene costo base conocido, su base nunca estuvo en el costo
    del snapshot: se descuenta el ingreso completo.
    Limitación: compras sin costo cargado no mueven el costo y se ven como
    rendimiento.
    """
    snaps: list[CryptoSnapshot] = (
        db.query(CryptoSnapshot)
        .filter(CryptoSnapshot.user_id == user_id, CryptoSnapshot.date >= since)
        .order_by(CryptoSnapshot.date.asc())
        .all()
    )
    if not snaps:
        return []
    sales = [
        (_sale_local_date(s.sold_at), s)
        for s in db.query(CryptoSale).filter(CryptoSale.user_id == user_id).all()
    ]

    out: list[dict] = []
    prev: Optional[CryptoSnapshot] = None
    for sn in snaps:
        rate = float(sn.dolar_rate or 0)
        if prev is None:
            flujo_usd = 0.0
            flujo_ars: Optional[float] = 0.0
        else:
            delta_cost = float(sn.cost_usd or 0) - float(prev.cost_usd or 0)
            ajuste = 0.0
            for sd, s in sales:
                if prev.date < sd <= sn.date:
                    if s.pnl_usd is not None:
                        ajuste += float(s.pnl_usd)
                    else:
                        ajuste += float(s.proceeds_usd or 0)
            flujo_usd = round(delta_cost - ajuste, 2)
            flujo_ars = round(flujo_usd * rate, 2) if rate else None
        out.append(
            {
                "id": sn.id,
                "date": sn.date,
                "taken_at": sn.taken_at,
                "total_usd": float(sn.total_usd or 0),
                "total_ars": float(sn.total_ars or 0),
                "cost_usd": float(sn.cost_usd or 0),
                "dolar_rate": rate,
                "flujo_usd": flujo_usd,
                "flujo_ars": flujo_ars,
            }
        )
        prev = sn
    return out
