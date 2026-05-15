"""Daily dolar quote upsert."""
from __future__ import annotations

import logging

from ..database import SessionLocal
from ..services import dolar_service

log = logging.getLogger(__name__)


async def run() -> int:
    db = SessionLocal()
    try:
        rows = await dolar_service.fetch_all(db)
        log.info("dolar_job: %s sources updated", len(rows))
        return len(rows)
    finally:
        db.close()
