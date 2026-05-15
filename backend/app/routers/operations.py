from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Operation, User
from ..schemas import OperationOut, OperationsSummary
from ..services import operations_service, pnl
from ..services.iol_auth import IolAuthError, IolNotConnectedError

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("", response_model=list[OperationOut])
def list_operations(
    year: int = Query(default=2026),
    event_kind: str | None = None,
    simbolo: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    desde = date(year, 1, 1)
    hasta = date(year, 12, 31)
    q = db.query(Operation).filter(
        Operation.user_id == user.id,
        Operation.fecha_operada >= desde,
        Operation.fecha_operada <= hasta,
    )
    if event_kind:
        kinds = [k.strip().upper() for k in event_kind.split(",") if k.strip()]
        if kinds:
            q = q.filter(Operation.event_kind.in_(kinds))
    if simbolo:
        q = q.filter(Operation.simbolo.ilike(f"%{simbolo}%"))
    return q.order_by(Operation.fecha_operada.desc(), Operation.id.desc()).all()


@router.post("/sync")
async def sync(
    year: int = Query(default=2026),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        n = await operations_service.sync_operations(db, user.id, year=year)
    except IolNotConnectedError:
        raise HTTPException(status_code=409, detail="IOL not connected")
    except IolAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"synced": n, "year": year}


@router.get("/summary", response_model=OperationsSummary)
def summary(
    year: int = Query(default=2026),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return pnl.operations_summary(db, user.id, year=year)
