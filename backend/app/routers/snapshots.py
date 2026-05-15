from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..jobs import snapshot_job
from ..models import PortfolioSnapshot, User
from ..schemas import SnapshotOut

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get("", response_model=list[SnapshotOut])
def list_snapshots(
    days: int = Query(default=180, ge=1, le=3650),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    since = date.today() - timedelta(days=days)
    return (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.user_id == user.id, PortfolioSnapshot.date >= since)
        .order_by(PortfolioSnapshot.date.asc())
        .all()
    )


@router.post("/run-now", response_model=SnapshotOut | None)
async def run_now(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = await snapshot_job.run(source="manual")
    if not result:
        raise HTTPException(status_code=409, detail="No se pudo generar snapshot (IOL no conectado o error)")
    row = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.id == result["id"], PortfolioSnapshot.user_id == user.id)
        .first()
    )
    return row


@router.delete("/{snapshot_id}")
def delete_snapshot(snapshot_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.id == snapshot_id, PortfolioSnapshot.user_id == user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    db.delete(row)
    db.commit()
    return {"deleted": snapshot_id}
