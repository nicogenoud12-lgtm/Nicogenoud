from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from .config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(sub: str, extra: dict | None = None) -> tuple[str, int]:
    now = datetime.now(tz=timezone.utc)
    expires_in = settings.jwt_expires_min * 60
    payload = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)
    return token, expires_in


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except JWTError as e:
        raise ValueError("Invalid token") from e
