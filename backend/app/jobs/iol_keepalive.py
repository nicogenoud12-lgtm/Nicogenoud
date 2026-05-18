"""Proactive IOL token keep-alive job.

Runs every 12 hours. For each connected user whose refresh token is within
7 days of expiry, forces a token rotation. Falls back to password grant if
the refresh fails. This ensures the session never expires from inactivity.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from ..database import SessionLocal
from ..models import IolCredential, OauthToken
from ..services import iol_auth
from ..crypto import decrypt

log = logging.getLogger(__name__)

_RENEW_WINDOW_DAYS = 7


async def run() -> None:
    db = SessionLocal()
    try:
        tokens = db.query(OauthToken).all()
        if not tokens:
            log.debug("iol_keepalive: no connected users, nothing to do")
            return

        now = datetime.now(tz=timezone.utc)
        renewed = 0
        for tok in tokens:
            user_id = tok.user_id
            try:
                refresh_exp = tok.refresh_expires_at
                if refresh_exp is not None:
                    if refresh_exp.tzinfo is None:
                        refresh_exp = refresh_exp.replace(tzinfo=timezone.utc)
                    # Only force-refresh if refresh token is near expiry or already expired
                    near_expiry = refresh_exp - now < timedelta(days=_RENEW_WINDOW_DAYS)
                else:
                    # No expiry info: always refresh proactively
                    near_expiry = True

                if near_expiry:
                    log.info("iol_keepalive: proactive refresh for user_id=%d", user_id)
                    await iol_auth.get_valid_access_token(db, user_id, force_refresh=True)
                else:
                    # Access token still healthy — just touch it to confirm
                    await iol_auth.get_valid_access_token(db, user_id, force_refresh=False)

                # Update keepalive timestamp
                db.refresh(tok)
                tok.last_keepalive_at = now
                db.commit()
                renewed += 1
                log.info("iol_keepalive: ok user_id=%d", user_id)
            except Exception as e:
                log.error("iol_keepalive: failed for user_id=%d: %s", user_id, e)
                cred = db.query(IolCredential).filter(IolCredential.user_id == user_id).first()
                if cred:
                    cred.last_error = f"keepalive {now.date()}: {str(e)[:400]}"
                    db.commit()

        log.info("iol_keepalive: done, %d/%d users renewed", renewed, len(tokens))
    finally:
        db.close()
