from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import scheduler as scheduler_mod
from ..crud import all_settings, set_setting
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import SettingsResponse, SettingsUpdate
from ..services.dolar_service import SUPPORTED_SOURCES

router = APIRouter(prefix="/settings", tags=["settings"])

ALLOWED_KEYS = {
    "dolar_source",
    "scheduler_enabled",
    "snapshot_cron",
    "dolar_cron_morning",
    "dolar_cron_evening",
    "tz",
    "operations_year",
}


@router.get("", response_model=SettingsResponse)
def get_settings(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return SettingsResponse(settings=all_settings(db))


@router.put("", response_model=SettingsResponse)
def update_settings(
    body: SettingsUpdate,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    needs_reschedule = False
    for k, v in body.settings.items():
        if k not in ALLOWED_KEYS:
            raise HTTPException(status_code=400, detail=f"Unknown setting key: {k}")
        if k == "dolar_source" and v not in SUPPORTED_SOURCES:
            raise HTTPException(
                status_code=400, detail=f"dolar_source must be one of {SUPPORTED_SOURCES}"
            )
        if k in {"scheduler_enabled", "snapshot_cron", "dolar_cron_morning", "dolar_cron_evening", "tz"}:
            needs_reschedule = True
        set_setting(db, k, v)
    db.commit()
    if needs_reschedule:
        try:
            scheduler_mod.reschedule()
        except Exception:
            pass
    return SettingsResponse(settings=all_settings(db))
