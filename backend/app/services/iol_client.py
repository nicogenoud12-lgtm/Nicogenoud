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
        """Fetch account movements (net amounts post-retention).

        IOL endpoint probed in order: /api/v2/MiCuenta/Movimientos,
        /api/v2/Cuenta/Movimientos. Returns empty list on 404 (degraded gracefully).
        """
        params = {
            "fechaDesde": desde.isoformat(),
            "fechaHasta": hasta.isoformat(),
        }
        for path in ("/api/v2/MiCuenta/Movimientos", "/api/v2/Cuenta/Movimientos"):
            try:
                result = await self._request("GET", path, params=params)
                if isinstance(result, list):
                    log.info("IOL %s returned %d movimientos", path, len(result))
                    return result
                if isinstance(result, dict):
                    for key in ("movimientos", "items", "data"):
                        if key in result and isinstance(result[key], list):
                            items = result[key]
                            log.info("IOL %s[%s] returned %d movimientos", path, key, len(items))
                            return items
                log.warning("IOL %s unexpected shape: %s", path, list(result.keys()) if isinstance(result, dict) else type(result))
                return []
            except Exception as e:
                log.warning("IOL %s failed (%s), trying next", path, e)
        log.warning("get_movimientos: all endpoints failed, returning []")
        return []
