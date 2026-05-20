from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Operation, User
from ..schemas import OperationOut, OperationsSummary
from ..services import operations_service, pnl
from ..services.dolar_service import build_mep_lookup, fx_for_date
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
    ops = q.order_by(Operation.fecha_operada.desc(), Operation.id.desc()).all()

    mep = build_mep_lookup(db, desde, hasta)
    sorted_dates = sorted(mep.keys())

    result = []
    for o in ops:
        rate = fx_for_date(mep, sorted_dates, o.fecha_operada) if o.fecha_operada else None
        amount = float(o.monto_neto) if o.monto_neto is not None else (float(o.monto_operado) if o.monto_operado is not None else None)
        is_usd = o.currency_kind in ("USD_MEP", "USD_CABLE")

        if amount is not None and rate and rate > 0:
            monto_ars = round(amount * rate, 2) if is_usd else round(amount, 2)
            monto_usd = round(amount, 2) if is_usd else round(amount / rate, 2)
        elif amount is not None:
            monto_ars = round(amount, 2) if not is_usd else None
            monto_usd = round(amount, 2) if is_usd else None
        else:
            monto_ars = None
            monto_usd = None

        out = OperationOut.model_validate(o)
        out.monto_ars = monto_ars
        out.monto_usd = monto_usd
        result.append(out)

    return result


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
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    year: int = Query(default=2026),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if from_date is None:
        from_date = date(year, 1, 1)
    if to_date is None:
        to_date = date(year, 12, 31)
    return pnl.operations_summary(db, user.id, from_date=from_date, to_date=to_date)
