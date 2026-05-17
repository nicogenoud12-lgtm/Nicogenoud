"""Binance public API — live 24h ticker + daily Klines.

Used as the primary source for crypto prices (1200 req/min limit, no API key
required for public market data). Optionally accepts BINANCE_API_KEY via env
to lift rate limits and reduce geo-blocking on cloud server IPs.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date, datetime, timezone

import httpx

log = logging.getLogger(__name__)

_BASE = "https://api.binance.com"
_TIMEOUT = 15


def _headers() -> dict[str, str]:
    """Optional API key for higher rate limits / fewer geo-blocks."""
    key = os.getenv("BINANCE_API_KEY", "").strip()
    return {"X-MBX-APIKEY": key} if key else {}

# CoinGecko ID → Binance quote asset (usually USDT; NEXO uses USDT too)
_CGID_TO_SYMBOL: dict[str, str] = {
    "bitcoin": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "binancecoin": "BNBUSDT",
    "solana": "SOLUSDT",
    "cardano": "ADAUSDT",
    "polkadot": "DOTUSDT",
    "litecoin": "LTCUSDT",
    "cosmos": "ATOMUSDT",
    "avalanche-2": "AVAXUSDT",
    "matic-network": "MATICUSDT",
    "chainlink": "LINKUSDT",
    "uniswap": "UNIUSDT",
    "ripple": "XRPUSDT",
    "dogecoin": "DOGEUSDT",
    "shiba-inu": "SHIBUSDT",
    "tron": "TRXUSDT",
    "stellar": "XLMUSDT",
    "vechain": "VETUSDT",
    "filecoin": "FILUSDT",
    "near": "NEARUSDT",
    "algorand": "ALGOUSDT",
    "hedera-hashgraph": "HBARUSDT",
    "internet-computer": "ICPUSDT",
    "nexo": "NEXOUSDT",
    "tether": "USDCUSDT",   # stable — price will be ~1
    "usd-coin": "USDCUSDT",
    "dai": "DAIUSDT",
    "optimism": "OPUSDT",
    "arbitrum": "ARBUSDT",
    "aptos": "APTUSDT",
    "sui": "SUIUSDT",
    "sei-network": "SEIUSDT",
    "injective-protocol": "INJUSDT",
    "celestia": "TIAUSDT",
    "pepe": "PEPEUSDT",
    "dogwifcoin": "WIFUSDT",
    "bonk": "BONKUSDT",
}


class BinanceError(RuntimeError):
    pass


async def get_prices(coingecko_ids: list[str]) -> dict[str, dict]:
    """Return {coingecko_id: {usd: float, usd_24h_change: float}} using Binance 24hr ticker.

    Coins without a Binance mapping are silently omitted from the result.
    """
    id_to_symbol: dict[str, str] = {}
    for cid in coingecko_ids:
        cid_lower = (cid or "").strip().lower()
        sym = _CGID_TO_SYMBOL.get(cid_lower)
        if sym:
            id_to_symbol[cid_lower] = sym

    if not id_to_symbol:
        return {}

    url = f"{_BASE}/api/v3/ticker/24hr"
    # Compact JSON (no spaces) is what Binance expects in the symbols param.
    params = {"symbols": json.dumps(list(id_to_symbol.values()), separators=(",", ":"))}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_headers()) as client:
            r = await client.get(url, params=params)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        body = (e.response.text or "")[:200]
        raise BinanceError(f"ticker failed: HTTP {e.response.status_code} {body}") from e
    except httpx.HTTPError as e:
        raise BinanceError(f"ticker failed: {e}") from e

    symbol_to_id = {v: k for k, v in id_to_symbol.items()}
    out: dict[str, dict] = {}
    for item in r.json() or []:
        sym = item.get("symbol")
        cid = symbol_to_id.get(sym)
        if not cid:
            continue
        try:
            price = float(item["lastPrice"])
            change = float(item["priceChangePercent"])
        except (KeyError, ValueError, TypeError):
            continue
        out[cid] = {"usd": price, "usd_24h_change": change}
    return out


async def get_7d_changes(coingecko_ids: list[str]) -> dict[str, float]:
    """Return {coingecko_id: pct_change_7d} computed from daily klines.

    One klines request per coin in parallel — well under Binance's rate limit.
    Coins without a Binance mapping or with <8 candles are omitted.
    """
    headers = _headers()

    async def fetch_one(client: httpx.AsyncClient, cid_lower: str) -> tuple[str, float | None]:
        symbol = _CGID_TO_SYMBOL.get(cid_lower)
        if not symbol:
            return cid_lower, None
        try:
            r = await client.get(
                f"{_BASE}/api/v3/klines",
                params={"symbol": symbol, "interval": "1d", "limit": "8"},
            )
            r.raise_for_status()
            data = r.json() or []
            if len(data) < 8:
                return cid_lower, None
            # data[0] is the oldest candle (~7 days ago), data[-1] is the current day.
            close_7d_ago = float(data[0][4])
            close_now = float(data[-1][4])
            if close_7d_ago == 0:
                return cid_lower, None
            return cid_lower, (close_now - close_7d_ago) / close_7d_ago * 100
        except (httpx.HTTPError, ValueError, IndexError, TypeError) as e:
            log.warning("binance 7d change failed for %s: %s", symbol, e)
            return cid_lower, None

    cids = [(cid or "").strip().lower() for cid in coingecko_ids]
    cids = [c for c in cids if c]
    if not cids:
        return {}
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=headers) as client:
        results = await asyncio.gather(*[fetch_one(client, c) for c in cids])
    return {cid: pct for cid, pct in results if pct is not None}


async def fetch_history_usd(coingecko_id: str, since: date, until: date) -> dict[date, float]:
    """Return {date: close_price_usd} for the given CoinGecko ID using Binance Klines.

    Returns empty dict if the coin has no Binance mapping.
    """
    symbol = _CGID_TO_SYMBOL.get((coingecko_id or "").strip().lower())
    if not symbol:
        log.debug("binance: no symbol mapping for coingecko_id=%s", coingecko_id)
        return {}

    ts_from = int(datetime(since.year, since.month, since.day, tzinfo=timezone.utc).timestamp() * 1000)
    ts_to = int(
        datetime(until.year, until.month, until.day, 23, 59, 59, tzinfo=timezone.utc).timestamp() * 1000
    )

    url = f"{_BASE}/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": "1d",
        "startTime": str(ts_from),
        "endTime": str(ts_to),
        "limit": "1000",
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_headers()) as client:
            r = await client.get(url, params=params)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        body = (e.response.text or "")[:200]
        raise BinanceError(f"klines failed for {symbol}: HTTP {e.response.status_code} {body}") from e
    except httpx.HTTPError as e:
        raise BinanceError(f"klines failed for {symbol}: {e}") from e

    # Each kline: [openTime, open, high, low, close, volume, closeTime, ...]
    out: dict[date, float] = {}
    for kline in r.json() or []:
        try:
            open_time_ms = kline[0]
            close_price = float(kline[4])
        except (IndexError, TypeError, ValueError):
            continue
        d = datetime.fromtimestamp(open_time_ms / 1000, tz=timezone.utc).date()
        out[d] = close_price
    return out
