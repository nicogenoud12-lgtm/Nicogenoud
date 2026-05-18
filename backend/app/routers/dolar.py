from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..crud import get_setting
from ..database import get_db
from ..deps import get_current_user
from ..models import DolarQuote, User
from ..schemas import DolarQuoteOut
from ..services import dolar_service
from ..services.dolar_service import backfill_historical_mep

router = APIRouter(prefix="/dolar", tags=["dolar"])


@router.get("/current", response_model=DolarQuoteOut)
async def current(
    source: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    src = source or (get_setting(db, "dolar_source", "MEP") or "MEP")
    row = await dolar_service.get_or_fetch(db, d=date.today(), source=src)
    return row


@router.post("/backfill")
async def backfill(
    desde: date,
    hasta: date,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Backfill historical MEP rates from ArgentinaDatos for the given date range."""
    inserted = await backfill_historical_mep(db, desde=desde, hasta=hasta)
    return {"inserted": inserted, "desde": str(desde), "hasta": str(hasta)}


@router.get("/history", response_model=list[DolarQuoteOut])
def history(
    source: str | None = None,
    days: int = Query(default=90, ge=1, le=3650),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    src = source or (get_setting(db, "dolar_source", "MEP") or "MEP")
    since = date.today() - timedelta(days=days)
    return (
        db.query(DolarQuote)
        .filter(DolarQuote.source == src, DolarQuote.date >= since)
        .order_by(DolarQuote.date.asc())
        .all()
    )
