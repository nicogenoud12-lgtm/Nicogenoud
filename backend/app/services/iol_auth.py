"""IOL OAuth2 token lifecycle."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..crypto import decrypt, encrypt
from ..models import IolCredential, OauthToken

log = logging.getLogger(__name__)


class IolNotConnectedError(Exception):
    pass


class IolAuthError(Exception):
    pass


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None
    access_expires_at: datetime
    refresh_expires_at: datetime | None


_user_locks: dict[int, asyncio.Lock] = {}


def _lock_for(user_id: int) -> asyncio.Lock:
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


def _parse_expiry(seconds: int | None, fallback_min: int = 14) -> datetime:
    sec = int(seconds) if seconds else fallback_min * 60
    return datetime.now(tz=timezone.utc) + timedelta(seconds=sec)


async def _post_token(form: dict) -> TokenSet:
    url = settings.iol_base_url.rstrip("/") + settings.iol_token_path
    async with httpx.AsyncClient(timeout=settings.iol_http_timeout) as client:
        r = await client.post(
            url,
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if r.status_code in (400, 401):
        try:
            payload = r.json()
        except ValueError:
            payload = {"detail": r.text}
        raise IolAuthError(payload.get("error_description") or payload.get("error") or str(payload))
    r.raise_for_status()
    data = r.json()
    return TokenSet(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        access_expires_at=_parse_expiry(data.get("expires_in")),
        refresh_expires_at=None,
    )


async def password_grant(username: str, password: str) -> TokenSet:
    return await _post_token(
        {"username": username, "password": password, "grant_type": "password"}
    )


async def refresh_grant(refresh_token: str) -> TokenSet:
    return await _post_token(
        {"refresh_token": refresh_token, "grant_type": "refresh_token"}
    )


def _persist_tokens(db: Session, user_id: int, ts: TokenSet) -> None:
    row = db.query(OauthToken).filter(OauthToken.user_id == user_id).first()
    if row is None:
        row = OauthToken(
            user_id=user_id,
            access_token_enc=encrypt(ts.access_token),
            refresh_token_enc=encrypt(ts.refresh_token) if ts.refresh_token else None,
            access_expires_at=ts.access_expires_at,
            refresh_expires_at=ts.refresh_expires_at,
        )
        db.add(row)
    else:
        row.access_token_enc = encrypt(ts.access_token)
        if ts.refresh_token:
            row.refresh_token_enc = encrypt(ts.refresh_token)
        row.access_expires_at = ts.access_expires_at
        row.refresh_expires_at = ts.refresh_expires_at
    db.commit()


async def connect_user(db: Session, user_id: int, iol_username: str, iol_password: str) -> None:
    ts = await password_grant(iol_username, iol_password)
    cred = db.query(IolCredential).filter(IolCredential.user_id == user_id).first()
    if cred is None:
        cred = IolCredential(
            user_id=user_id,
            iol_username=iol_username,
            iol_password_enc=encrypt(iol_password),
        )
        db.add(cred)
    else:
        cred.iol_username = iol_username
        cred.iol_password_enc = encrypt(iol_password)
        cred.last_error = None
    _persist_tokens(db, user_id, ts)


async def disconnect_user(db: Session, user_id: int) -> None:
    db.query(OauthToken).filter(OauthToken.user_id == user_id).delete()
    db.query(IolCredential).filter(IolCredential.user_id == user_id).delete()
    db.commit()


async def get_valid_access_token(db: Session, user_id: int, *, force_refresh: bool = False) -> str:
    """Return a valid IOL access token for user_id, refreshing if needed.

    Acquires a per-user asyncio.Lock to avoid concurrent refreshes from
    invalidating each other's refresh tokens.
    """
    async with _lock_for(user_id):
        token_row = db.query(OauthToken).filter(OauthToken.user_id == user_id).first()
        cred = db.query(IolCredential).filter(IolCredential.user_id == user_id).first()

        if token_row is None and cred is None:
            raise IolNotConnectedError("IOL not connected")

        now = datetime.now(tz=timezone.utc)
        if token_row is not None and not force_refresh:
            # Tolerate naive datetimes from older SQLite rows
            exp = token_row.access_expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp - now > timedelta(seconds=120):
                return decrypt(token_row.access_token_enc)

        # Try refresh first
        if token_row is not None and token_row.refresh_token_enc is not None:
            try:
                ts = await refresh_grant(decrypt(token_row.refresh_token_enc))
                _persist_tokens(db, user_id, ts)
                return ts.access_token
            except (IolAuthError, httpx.HTTPError) as e:
                log.warning("refresh failed for user_id=%s: %s — falling back to password", user_id, e)

        # Fallback: re-issue with stored credentials
        if cred is None:
            raise IolNotConnectedError("IOL refresh failed and no stored credentials")
        try:
            ts = await password_grant(cred.iol_username, decrypt(cred.iol_password_enc))
        except IolAuthError as e:
            cred.last_error = str(e)[:500]
            db.commit()
            raise
        cred.last_error = None
        _persist_tokens(db, user_id, ts)
        return ts.access_token
