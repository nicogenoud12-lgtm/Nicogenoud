from cryptography.fernet import Fernet, InvalidToken

from .config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not settings.fernet_key:
            raise RuntimeError("FERNET_KEY is not set")
        _fernet = Fernet(settings.fernet_key.encode())
    return _fernet


def encrypt(plain: str) -> bytes:
    return _get_fernet().encrypt(plain.encode())


def decrypt(blob: bytes) -> str:
    try:
        return _get_fernet().decrypt(blob).decode()
    except InvalidToken as e:
        raise RuntimeError("Failed to decrypt: invalid FERNET_KEY or corrupt data") from e
