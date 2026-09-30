"""Resumen diario con IA: se genera después del cierre del mercado."""
from __future__ import annotations

import logging

from ..crud import get_first_user
from ..database import SessionLocal
from ..services import ai_insights

log = logging.getLogger(__name__)


async def run() -> None:
    if not ai_insights.is_enabled():
        return
    db = SessionLocal()
    try:
        user = get_first_user(db)
        if user is None:
            return
        await ai_insights.generate(db, user.id, source="scheduler")
    except Exception:
        log.exception("ai insight job failed")
    finally:
        db.close()
