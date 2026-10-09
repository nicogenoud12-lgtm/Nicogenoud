"""Tareas largas en segundo plano.

Cloudflare Tunnel corta cualquier request que tarde más de ~100 s, y traer el
historial o los precios de todos los activos tarda más. El request sólo lanza
la tarea y devuelve su estado; el frontend la consulta hasta que termina.

El registro vive en memoria: uvicorn corre con un solo proceso, y si el
backend se reinicia a mitad de una tarea alcanza con volver a lanzarla (todo
lo que hacen es idempotente).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable

from sqlalchemy.orm import Session

from ..database import SessionLocal
from .iol_auth import IolAuthError, IolNotConnectedError

log = logging.getLogger(__name__)

Progress = Callable[[str], None]
JobFn = Callable[[Session, Progress], Awaitable[dict]]

_jobs: dict[tuple[int, str], dict] = {}
_tasks: set[asyncio.Task] = set()


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def get(user_id: int, kind: str) -> dict:
    return _jobs.get((user_id, kind)) or {"estado": None}


def start(user_id: int, kind: str, fn: JobFn) -> dict:
    """Lanza la tarea si no hay una igual corriendo; devuelve su estado."""
    current = _jobs.get((user_id, kind))
    if current and current["estado"] == "corriendo":
        return current
    job = {"estado": "corriendo", "paso": None, "resultado": None, "error": None, "inicio": _now(), "fin": None}
    _jobs[(user_id, kind)] = job

    def progress(paso: str) -> None:
        job["paso"] = paso

    async def runner() -> None:
        db = SessionLocal()
        try:
            job["resultado"] = await fn(db, progress)
            job["estado"] = "ok"
        except IolNotConnectedError:
            job["estado"], job["error"] = "error", "IOL no está conectado"
        except IolAuthError as e:
            job["estado"], job["error"] = "error", f"IOL rechazó el login: {e}"
        except Exception as e:  # la tarea no tiene a quién propagarle el error
            log.exception("background job %s failed (user=%d)", kind, user_id)
            job["estado"], job["error"] = "error", str(e)[:300] or e.__class__.__name__
        finally:
            db.close()
            job["fin"] = _now()

    task = asyncio.create_task(runner())
    _tasks.add(task)  # sin referencia fuerte el event loop puede descartarla
    task.add_done_callback(_tasks.discard)
    return job
