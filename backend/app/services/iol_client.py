"""IOL REST client with retries and 401-refresh."""
from __future__ import annotations

import logging
from datetime import date

import httpx
from sqlalchemy.orm import Session
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import settings
from . import iol_auth

log = logging.getLogger(__name__)


class RateLimitError(Exception):
    pass


class IolApiError(Exception):
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"IOL API error {status_code}: {payload}")


class IolClient:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self._client = httpx.AsyncClient(
            base_url=settings.iol_base_url,
            timeout=settings.iol_http_timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aclose()

    async def _auth_headers(self, *, force_refresh: bool = False) -> dict:
        token = await iol_auth.get_valid_access_token(
            self.db, self.user_id, force_refresh=force_refresh
        )
        return {"Authorization": f"Bearer {token}"}

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=0.5, max=8),
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.NetworkError, RateLimitError)
        ),
    )
    async def _request(self, method: str, path: str, **kwargs) -> dict | list:
        headers = await self._auth_headers()
        headers.update(kwargs.pop("headers", {}))
        r = await self._client.request(method, path, headers=headers, **kwargs)
        if r.status_code == 401:
            log.info("IOL 401 — forcing refresh and retrying once")
            headers = await self._auth_headers(force_refresh=True)
            r = await self._client.request(method, path, headers=headers, **kwargs)
        if r.status_code == 429:
            raise RateLimitError(r.headers.get("Retry-After", "1"))
        if 500 <= r.status_code < 600:
            raise httpx.NetworkError(f"upstream 5xx: {r.status_code}")
        if r.status_code >= 400:
            try:
                payload = r.json()
            except ValueError:
                payload = r.text
            raise IolApiError(r.status_code, payload)
        if r.status_code == 204 or not r.content:
            return {}
        try:
            return r.json()
        except ValueError:
            return {"raw": r.text}

    # ---- Endpoints ----

    async def get_portafolio(self, pais: str) -> dict:
        return await self._request("GET", f"/api/v2/portafolio/{pais}")

    async def get_estado_cuenta(self) -> dict:
        return await self._request("GET", "/api/v2/estadocuenta")

    async def get_operaciones(
        self,
        *,
        estado: str = "terminadas",
        desde: date,
        hasta: date,
        pais: str | None = None,
    ) -> list:
        params = {
            "filtro.estado": estado,
            "filtro.fechaDesde": desde.isoformat(),
            "filtro.fechaHasta": hasta.isoformat(),
        }
        if pais:
            params["filtro.pais"] = pais
        log.info(
            "IOL GET /api/v2/operaciones params=%s",
            {k: v for k, v in params.items()},
        )
        result = await self._request("GET", "/api/v2/operaciones", params=params)
        if isinstance(result, dict) and "operaciones" in result:
            ops = result["operaciones"]
        elif isinstance(result, list):
            ops = result
        else:
            ops = []
        log.info("IOL /api/v2/operaciones returned %d rows", len(ops))
        return ops

    async def get_cotizacion(self, mercado: str, simbolo: str) -> dict:
        return await self._request(
            "GET", f"/api/v2/{mercado}/Titulos/{simbolo}/Cotizacion"
        )

    async def get_movimientos(self, *, desde: date, hasta: date) -> list:
        """Fetch account movements in 30-day chunks to avoid IOL 500 on long ranges."""
        from datetime import timedelta

        all_items: list = []
        chunk_start = desde
        while chunk_start <= hasta:
            chunk_end = min(chunk_start + timedelta(days=29), hasta)
            chunk = await self._get_movimientos_chunk(chunk_start, chunk_end)
            all_items.extend(chunk)
            chunk_start = chunk_end + timedelta(days=1)
        log.info("get_movimientos: total=%d for %s→%s", len(all_items), desde, hasta)
        return all_items

    async def _get_movimientos_chunk(self, desde: date, hasta: date) -> list:
        attempts = [
            ("/api/v2/MiCuenta/Movimientos",  {"fechaDesde": desde.isoformat(), "fechaHasta": hasta.isoformat()}),
            ("/api/v2/Cuenta/Movimientos",     {"fechaDesde": desde.isoformat(), "fechaHasta": hasta.isoformat()}),
            ("/api/v2/MiCuenta/Movimientos",   {"filtro.fechaDesde": desde.isoformat(), "filtro.fechaHasta": hasta.isoformat()}),
            ("/api/v2/movimientos",            {"fechaDesde": desde.isoformat(), "fechaHasta": hasta.isoformat()}),
        ]
        for path, params in attempts:
            try:
                result = await self._request("GET", path, params=params)
                if isinstance(result, list):
                    log.info("IOL %s [%s→%s] returned %d items", path, desde, hasta, len(result))
                    return result
                if isinstance(result, dict):
                    for key in ("movimientos", "items", "data"):
                        if key in result and isinstance(result[key], list):
                            items = result[key]
                            log.info("IOL %s[%s] [%s→%s] returned %d items", path, key, desde, hasta, len(items))
                            return items
                    log.warning("IOL %s unexpected shape keys=%s", path, list(result.keys()))
                    return []
            except Exception as e:
                log.warning("IOL %s [%s→%s] failed (%s), trying next", path, desde, hasta, e)
        log.warning("_get_movimientos_chunk: all endpoints failed for %s→%s", desde, hasta)
        return []
