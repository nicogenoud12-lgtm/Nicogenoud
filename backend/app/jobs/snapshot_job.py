"""Daily snapshot job: refresh holdings, snapshot portfolio."""
from __future__ import annotations

import logging
from datetime import date

from ..crud import get_first_user, get_setting
from ..database import SessionLocal
from ..models import IolCredential
from ..services import dolar_service, portfolio_service

log = logging.getLogger(__name__)


async def run(source: str = "scheduler", on_date: date | None = None) -> dict | None:
    db = SessionLocal()
    try:
        user = get_first_user(db)
        if user is None:
            log.info("snapshot: no user yet")
            return None
        cred = db.query(IolCredential).filter(IolCredential.user_id == user.id).first()
        if cred is None:
            log.info("snapshot: IOL not connected, skipping")
            return None
        dolar_source = get_setting(db, "dolar_source", "MEP") or "MEP"
        try:
            await portfolio_service.refresh_holdings(db, user.id)
        except Exception as e:
            log.exception("snapshot: refresh_holdings failed")
            cred.last_error = str(e)[:500]
            db.commit()
            return None
        try:
            dq = await dolar_service.get_or_fetch(db, d=on_date or date.today(), source=dolar_source)
            dolar_rate = float(dq.promedio) if dq else 0.0
        except Exception:
            log.exception("snapshot: dolar fetch failed")
            dolar_rate = 0.0

        snap = portfolio_service.save_snapshot(
            db,
            user.id,
            on_date=on_date,
            dolar_rate=dolar_rate,
            dolar_source=dolar_source,
            source=source,
        )
        log.info("snapshot ok user=%s date=%s ars=%s usd=%s", user.id, snap.date, snap.total_ars, snap.total_usd)
        return {
            "id": snap.id,
            "date": snap.date.isoformat(),
            "total_ars": float(snap.total_ars),
            "total_usd": float(snap.total_usd),
        }
    finally:
        db.close()
