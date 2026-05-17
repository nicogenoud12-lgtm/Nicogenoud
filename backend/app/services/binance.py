"""Binance public API — live 24h ticker + daily Klines.

Used as a fallback when CoinGecko rate-limits requests.
No API key required for public market data.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone

import httpx

log = logging.getLogger(__name__)

_BASE = "https://api.binance.com"
_TIMEOUT = 15

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
    params = {"symbols": json.dumps(list(id_to_symbol.values()))}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(url, params=params)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise BinanceError(f"ticker failed: HTTP {e.response.status_code}") from e
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
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(url, params=params)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise BinanceError(f"klines failed for {symbol}: HTTP {e.response.status_code}") from e
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
