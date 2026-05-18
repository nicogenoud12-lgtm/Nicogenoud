from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..crud import get_setting
from ..database import get_db
from ..deps import get_current_user
from ..models import Holding, User
from ..schemas import HoldingOut, KpisResponse
from ..services import dolar_service, portfolio_service
from ..services.iol_auth import IolAuthError, IolNotConnectedError

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/holdings", response_model=list[HoldingOut])
async def list_holdings(
    refresh: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if refresh:
        try:
            await portfolio_service.refresh_holdings(db, user.id)
        except IolNotConnectedError:
            raise HTTPException(status_code=409, detail="IOL not connected")
        except IolAuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
    rows = (
        db.query(Holding)
        .filter(Holding.user_id == user.id)
        .order_by(Holding.valuacion_ars.desc())
        .all()
    )
    return rows


@router.get("/kpis", response_model=KpisResponse)
async def kpis(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dolar_source = get_setting(db, "dolar_source", "MEP") or "MEP"
    dolar_rate = 0.0
    try:
        dq = await dolar_service.get_or_fetch(db, d=date.today(), source=dolar_source)
        dolar_rate = float(dq.promedio) if dq else 0.0
    except Exception:
        pass
    data = portfolio_service.compute_kpis(
        db, user.id, dolar_rate=dolar_rate, dolar_source=dolar_source
    )
    return data


@router.get("/upcoming-events", response_model=list[dict[str, Any]])
def upcoming_events(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return portfolio_service.upcoming_events(db, user.id)
