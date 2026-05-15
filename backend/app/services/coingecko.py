"""CoinGecko v3 client: coin search + simple price (USD, with 24h change).

Free public endpoints, no API key. Light in-memory cache for prices to keep
us well under the 30 req/min rate limit during normal page reloads.
"""
from __future__ import annotations

import logging
import time
from typing import Iterable

import httpx

log = logging.getLogger(__name__)

_BASE = "https://api.coingecko.com/api/v3"
_TIMEOUT = 15
_PRICE_TTL = 60.0  # seconds
_SEARCH_TTL = 600.0  # 10 min

_price_cache: dict[tuple, tuple[float, dict]] = {}
_search_cache: dict[str, tuple[float, list]] = {}


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


def invalidate_cache() -> None:
    _price_cache.clear()
    _search_cache.clear()
