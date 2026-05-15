"""Daily operations sync (idempotent)."""
from __future__ import annotations

import logging
from datetime import date

from ..crud import get_first_user, get_setting
from ..database import SessionLocal
from ..models import IolCredential
from ..services import operations_service

log = logging.getLogger(__name__)


async def run(year: int | None = None) -> int:
    db = SessionLocal()
    try:
        user = get_first_user(db)
        if user is None:
            return 0
        cred = db.query(IolCredential).filter(IolCredential.user_id == user.id).first()
        if cred is None:
            log.info("operations_sync: IOL not connected, skipping")
            return 0
        target_year = year or int(get_setting(db, "operations_year", "2026") or 2026)
        n = await operations_service.sync_operations(db, user.id, year=target_year)
        log.info("operations_sync: %s rows touched (year=%s)", n, target_year)
        return n
    finally:
        db.close()
