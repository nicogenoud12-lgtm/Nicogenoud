from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..jobs import snapshot_job
from ..models import Holding, PortfolioSnapshot, User
from ..schemas import SnapshotOut
from ..services.classifier import classify_asset
from ..services.pnl import net_flows

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get("", response_model=list[SnapshotOut])
def list_snapshots(
    days: int = Query(default=180, ge=1, le=3650),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    since = date.today() - timedelta(days=days)
    rows = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.user_id == user.id, PortfolioSnapshot.date >= since)
        .order_by(PortfolioSnapshot.date.asc())
        .all()
    )
    if not rows:
        return []
    # El primer punto necesita el snapshot anterior (fuera de la ventana) como base
    before = (
        db.query(PortfolioSnapshot.date)
        .filter(PortfolioSnapshot.user_id == user.id, PortfolioSnapshot.date < rows[0].date)
        .order_by(PortfolioSnapshot.date.desc())
        .first()
    )
    return _with_flows(db, user.id, rows, before[0] if before else None)


def _with_flows(db: Session, user_id: int, rows: list, prev_date: date | None) -> list[SnapshotOut]:
    """Asigna a cada snapshot los flujos con fecha en (snapshot anterior, snapshot]."""
    flows = []
    if prev_date is not None:
        flows = net_flows(db, user_id, from_date=prev_date + timedelta(days=1), to_date=rows[-1].date)

    # Clase de cada símbolo según las tenencias registradas (misma clase que usa el gráfico)
    clase_by_sym: dict[str, str] = {}
    for r in rows:
        for h in r.breakdown_json or []:
            if h.get("simbolo") and h.get("clase"):
                clase_by_sym[h["simbolo"]] = h["clase"]
    for h in db.query(Holding).filter(Holding.user_id == user_id).all():
        clase_by_sym[h.simbolo] = h.clase

    out = []
    for r in rows:
        snap = SnapshotOut.model_validate(r)
        if prev_date is not None:
            por_clase: dict[str, dict[str, float]] = {}
            for f in flows:
                if not (prev_date < f["fecha"] <= r.date):
                    continue
                snap.flujo_ars += f["ars"]
                snap.flujo_usd += f["usd"]
                sym = f["simbolo"] or ""
                clase = clase_by_sym.get(sym) or classify_asset(simbolo=sym, descripcion=f["descripcion"])
                c = por_clase.setdefault(clase, {"ars": 0.0, "usd": 0.0})
                c["ars"] += f["ars"]
                c["usd"] += f["usd"]
            snap.flujo_ars = round(snap.flujo_ars, 2)
            snap.flujo_usd = round(snap.flujo_usd, 2)
            snap.flujo_por_clase = {
                k: {"ars": round(v["ars"], 2), "usd": round(v["usd"], 2)} for k, v in por_clase.items()
            }
        out.append(snap)
        prev_date = r.date
    return out


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


@router.delete("/by-date/{date_str}")
def delete_snapshot_by_date(
    date_str: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        target = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=422, detail="Formato de fecha inválido, usar YYYY-MM-DD")
    row = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.user_id == user.id, PortfolioSnapshot.date == target)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    deleted_id = row.id
    db.delete(row)
    db.commit()
    return {"deleted": deleted_id, "date": date_str}


@router.delete("/by-range/{desde}/{hasta}")
def delete_snapshots_by_range(
    desde: str,
    hasta: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        d_desde = date.fromisoformat(desde)
        d_hasta = date.fromisoformat(hasta)
    except ValueError:
        raise HTTPException(status_code=422, detail="Formato de fecha inválido, usar YYYY-MM-DD")
    rows = (
        db.query(PortfolioSnapshot)
        .filter(
            PortfolioSnapshot.user_id == user.id,
            PortfolioSnapshot.date >= d_desde,
            PortfolioSnapshot.date <= d_hasta,
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No snapshots in range")
    deleted_ids = [r.id for r in rows]
    for r in rows:
        db.delete(r)
    db.commit()
    return {"deleted": deleted_ids, "desde": desde, "hasta": hasta}


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
