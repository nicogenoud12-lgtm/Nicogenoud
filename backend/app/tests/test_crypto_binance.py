"""Tests for services/binance.py — mapeo de símbolos y robustez del batch (HTTP mockeado)."""
import asyncio
import json
from datetime import date

import httpx
import pytest

from app.services import binance


def _ticker(symbol: str, price: float, change: float = 1.5) -> dict:
    return {"symbol": symbol, "lastPrice": str(price), "priceChangePercent": str(change)}


@pytest.fixture()
def mock_http(monkeypatch):
    """Reemplaza httpx.AsyncClient por uno con MockTransport. Devuelve la lista
    de requests hechas; el handler se setea con `mock_http.handler = fn`."""
    real_client = httpx.AsyncClient
    calls: list[httpx.Request] = []

    class State:
        handler = None

    def transport_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if State.handler is None:
            raise AssertionError(f"request inesperada: {request.url}")
        return State.handler(request)

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(transport_handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    State.calls = calls
    return State


def test_tether_is_one_without_http(mock_http):
    out = asyncio.run(binance.get_prices(["tether"]))
    assert out == {"tether": {"usd": 1.0, "usd_24h_change": 0.0}}
    assert mock_http.calls == []


def test_usdt_and_usdc_are_not_collapsed(mock_http):
    def handler(request):
        symbols = json.loads(request.url.params["symbols"])
        assert symbols == ["USDCUSDT"]
        return httpx.Response(200, json=[_ticker("USDCUSDT", 0.9998, 0.01)])

    mock_http.handler = handler
    out = asyncio.run(binance.get_prices(["tether", "usd-coin"]))
    assert out["tether"]["usd"] == 1.0
    assert out["usd-coin"]["usd"] == pytest.approx(0.9998)


def test_matic_and_pol_map_to_polusdt(mock_http):
    def handler(request):
        symbols = json.loads(request.url.params["symbols"])
        assert symbols == ["POLUSDT"]  # deduplicado
        return httpx.Response(200, json=[_ticker("POLUSDT", 0.25)])

    mock_http.handler = handler
    out = asyncio.run(binance.get_prices(["matic-network", "polygon-ecosystem-token"]))
    assert out["matic-network"]["usd"] == pytest.approx(0.25)
    assert out["polygon-ecosystem-token"]["usd"] == pytest.approx(0.25)


def test_invalid_symbol_in_batch_falls_back_to_per_symbol(mock_http):
    def handler(request):
        if "symbols" in request.url.params:
            return httpx.Response(400, json={"code": -1121, "msg": "Invalid symbol."})
        sym = request.url.params["symbol"]
        if sym == "ETHUSDT":
            return httpx.Response(400, json={"code": -1121, "msg": "Invalid symbol."})
        return httpx.Response(200, json=_ticker(sym, 60000.0))

    mock_http.handler = handler
    out = asyncio.run(binance.get_prices(["bitcoin", "ethereum"]))
    assert out == {"bitcoin": {"usd": 60000.0, "usd_24h_change": 1.5}}
    # 1 batch + 2 individuales
    assert len(mock_http.calls) == 3


def test_other_http_errors_still_raise(mock_http):
    mock_http.handler = lambda request: httpx.Response(451, text="geo-blocked")
    with pytest.raises(binance.BinanceError):
        asyncio.run(binance.get_prices(["bitcoin"]))


def test_tether_history_is_flat_one(mock_http):
    out = asyncio.run(binance.fetch_history_usd("tether", date(2026, 1, 1), date(2026, 1, 3)))
    assert out == {date(2026, 1, 1): 1.0, date(2026, 1, 2): 1.0, date(2026, 1, 3): 1.0}
    assert mock_http.calls == []
