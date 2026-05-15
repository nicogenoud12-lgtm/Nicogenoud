"""Daily crypto snapshot job: pulls live prices and saves a row in
crypto_snapshots for any user that has at least one holding with a
resolvable coingecko_id."""
from __future__ import annotations

import logging

from sqlalchemy import select

from ..database import SessionLocal
from ..models import CryptoHolding, User
from ..services import crypto_service

log = logging.getLogger(__name__)


async def run() -> None:
    db = SessionLocal()
    try:
        user_ids = [
            uid
            for (uid,) in db.execute(
                select(CryptoHolding.user_id).distinct()
            ).all()
        ]
        for uid in user_ids:
            user = db.get(User, uid)
            if user is None:
                continue
            try:
                report = await crypto_service.build_report_and_snapshot(db, uid)
                log.info(
                    "crypto snapshot ok user=%s total_usd=%.2f items=%d",
                    uid,
                    report["total_value_usd"],
                    len(report["items"]),
                )
            except Exception:
                log.exception("crypto snapshot failed user=%s", uid)
    finally:
        db.close()
