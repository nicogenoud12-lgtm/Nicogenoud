from sqlalchemy.orm import Session

from .models import AppSetting, User


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_first_user(db: Session) -> User | None:
    return db.query(User).order_by(User.id.asc()).first()


def get_setting(db: Session, key: str, default: str | None = None) -> str | None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else default


def set_setting(db: Session, key: str, value: str) -> AppSetting:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is None:
        row = AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.flush()
    return row


def all_settings(db: Session) -> dict[str, str]:
    return {row.key: row.value for row in db.query(AppSetting).all()}
