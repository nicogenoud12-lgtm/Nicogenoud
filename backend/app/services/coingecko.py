"""CoinGecko v3 client: coin search + simple price (USD, with 24h change).

Free public endpoints, no API key. Light in-memory cache for prices to keep
us well under the 30 req/min rate limit during normal page reloads.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from typing import Iterable

import httpx

log = logging.getLogger(__name__)

_BASE = "https://api.coingecko.com/api/v3"
_TIMEOUT = 15
_PRICE_TTL = 60.0  # seconds
_SEARCH_TTL = 600.0  # 10 min

_price_cache: dict[tuple, tuple[float, dict]] = {}
_search_cache: dict[str, tuple[float, list]] = {}


# Well-known symbol → CoinGecko ID. Used to auto-resolve holdings that were
# added without going through the search picker.
KNOWN_IDS: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "ADA": "cardano",
    "DOT": "polkadot",
    "LTC": "litecoin",
    "ATOM": "cosmos",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "POL": "matic-network",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "XRP": "ripple",
    "DOGE": "dogecoin",
    "SHIB": "shiba-inu",
    "TRX": "tron",
    "XLM": "stellar",
    "VET": "vechain",
    "FIL": "filecoin",
    "NEAR": "near",
    "ALGO": "algorand",
    "HBAR": "hedera-hashgraph",
    "ICP": "internet-computer",
    "NEXO": "nexo",
    "USDT": "tether",
    "USDC": "usd-coin",
    "BUSD": "binance-usd",
    "DAI": "dai",
    "OP": "optimism",
    "ARB": "arbitrum",
    "APT": "aptos",
    "SUI": "sui",
    "SEI": "sei-network",
    "INJ": "injective-protocol",
    "TIA": "celestia",
    "PEPE": "pepe",
    "WIF": "dogwifcoin",
    "BONK": "bonk",
}


def resolve_id(symbol: str) -> str | None:
    """Return the CoinGecko ID for a well-known symbol, or None."""
    return KNOWN_IDS.get((symbol or "").strip().upper())


class CoinGeckoError(RuntimeError):
    pass


async def search(query: str, limit: int = 12) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []
    now = time.monotonic()
    key = q.lower()
    cached = _search_cache.get(key)
    if cached and cached[0] > now:
        return cached[1][:limit]

    url = f"{_BASE}/search"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(url, params={"query": q})
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise CoinGeckoError(f"search failed: {e}") from e
    data = r.json() or {}
    coins = data.get("coins") or []
    out = [
        {
            "id": c.get("id"),
            "symbol": (c.get("symbol") or "").upper(),
            "name": c.get("name"),
            "thumb": c.get("thumb"),
            "market_cap_rank": c.get("market_cap_rank"),
        }
        for c in coins
        if c.get("id") and c.get("symbol")
    ]
    _search_cache[key] = (now + _SEARCH_TTL, out)
    return out[:limit]


async def get_prices(
    ids: Iterable[str],
    vs_currencies: list[str] | None = None,
    include_24h_change: bool = True,
) -> dict[str, dict]:
    """Return {coingecko_id_lower: {usd, ars, usd_24h_change, ...}}."""
    id_list = sorted({s for s in ((i or "").strip().lower() for i in ids) if s})
    if not id_list:
        return {}
    vs = sorted({c.lower() for c in (vs_currencies or ["usd"])})
    key = (tuple(id_list), tuple(vs), bool(include_24h_change))

    now = time.monotonic()
    cached = _price_cache.get(key)
    if cached and cached[0] > now:
        return cached[1]

    params: dict[str, str] = {
        "ids": ",".join(id_list),
        "vs_currencies": ",".join(vs),
    }
    if include_24h_change:
        params["include_24hr_change"] = "true"

    url = f"{_BASE}/simple/price"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(url, params=params)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise CoinGeckoError(f"prices failed: {e}") from e
    data = r.json() or {}
    _price_cache[key] = (now + _PRICE_TTL, data)
    return data


async def fetch_history_usd(coingecko_id: str, since: date, until: date) -> dict[date, float]:
    """Return {date: usd_close_price} for the given coin over [since, until].

    Uses /coins/{id}/market_chart/range with vs_currency=usd. For ranges > 90
    days, CoinGecko returns daily granularity automatically.
    """
    cid = (coingecko_id or "").strip().lower()
    if not cid:
        return {}
    ts_from = int(datetime(since.year, since.month, since.day, tzinfo=timezone.utc).timestamp())
    ts_to = int(
        datetime(until.year, until.month, until.day, 23, 59, 59, tzinfo=timezone.utc).timestamp()
    )
    url = f"{_BASE}/coins/{cid}/market_chart/range"
    params = {"vs_currency": "usd", "from": str(ts_from), "to": str(ts_to)}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(url, params=params)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise CoinGeckoError(f"history failed for {cid}: {e}") from e
    data = r.json() or {}
    out: dict[date, float] = {}
    for entry in data.get("prices") or []:
        try:
            ts_ms, price = entry[0], entry[1]
        except (IndexError, TypeError):
            continue
        d = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date()
        # Keep the last sample for each date (closest to end of day)
        out[d] = float(price)
    return out


def invalidate_cache() -> None:
    _price_cache.clear()
    _search_cache.clear()
