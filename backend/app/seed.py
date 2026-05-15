"""Idempotent seed: ensure admin user + default AppSettings exist."""
from .config import settings
from .crud import get_setting, set_setting
from .database import SessionLocal
from .models import User
from .security import hash_password


DEFAULT_SETTINGS = {
    "dolar_source": "MEP",
    "scheduler_enabled": "true",
    "snapshot_cron": "55 23 * * *",
    "dolar_cron_morning": "0 8 * * *",
    "dolar_cron_evening": "50 23 * * *",
    "tz": "America/Argentina/Buenos_Aires",
    "operations_year": "2026",
}


def seed() -> None:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == settings.admin_username).first()
        if admin is None:
            admin = User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                is_admin=True,
            )
            db.add(admin)
            print(f"[seed] admin user created: {settings.admin_username}")
        else:
            print(f"[seed] admin user already exists: {settings.admin_username}")

        for key, value in DEFAULT_SETTINGS.items():
            if get_setting(db, key) is None:
                set_setting(db, key, value)
        db.commit()
        print("[seed] settings ensured")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
