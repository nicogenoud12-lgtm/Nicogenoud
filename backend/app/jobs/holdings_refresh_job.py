"""Periodic holdings refresh: keeps in-DB holdings current without saving a snapshot."""
from __future__ import annotations

import logging

from ..crud import get_first_user
from ..database import SessionLocal
from ..models import IolCredential
from ..services import portfolio_service

log = logging.getLogger(__name__)


async def run() -> None:
    db = SessionLocal()
    try:
        user = get_first_user(db)
        if user is None:
            return
        cred = db.query(IolCredential).filter(IolCredential.user_id == user.id).first()
        if cred is None:
            return
        await portfolio_service.refresh_holdings(db, user.id)
        log.info("holdings refresh ok user=%s", user.id)
    except Exception:
        log.exception("holdings refresh failed")
    finally:
        db.close()
