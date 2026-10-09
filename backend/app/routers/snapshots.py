import re
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..jobs import snapshot_job
from ..models import Holding, PortfolioSnapshot, User
from ..schemas import SnapshotOut
from ..services import history_service, portfolio_service
from ..services.classifier import classify_asset
from ..services.dolar_service import build_mep_lookup, fx_for_date
from ..services.iol_auth import IolAuthError, IolNotConnectedError
from ..services.ons_whitelist import normalize_ticker
from ..services.pnl import amortization_events, income_events, net_flows

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

_USD_MARKER = re.compile(r"\s+(US\$|USD|U\$S)$", re.IGNORECASE)


@router.get("", response_model=list[SnapshotOut])
def list_snapshots(
    days: int = Query(default=180, ge=1, le=3650),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    since = date.today() - timedelta(days=days)
    rows = (
        db.query(PortfolioSnapshot)
        .filter(
            PortfolioSnapshot.user_id == user.id,
            PortfolioSnapshot.date >= since,
            # Snapshots en 0 (guardados cuando IOL falló) no son datos reales: se omiten
            PortfolioSnapshot.total_ars > 0,
        )
        .order_by(PortfolioSnapshot.date.asc())
        .all()
    )
    if not rows:
        return []
    # El primer punto necesita el snapshot anterior (fuera de la ventana) como base
    before = (
        db.query(PortfolioSnapshot.date)
        .filter(
            PortfolioSnapshot.user_id == user.id,
            PortfolioSnapshot.date < rows[0].date,
            PortfolioSnapshot.total_ars > 0,
        )
        .order_by(PortfolioSnapshot.date.desc())
        .first()
    )
    return _with_flows(db, user.id, rows, before[0] if before else None)


def _with_flows(db: Session, user_id: int, rows: list, prev_date: date | None) -> list[SnapshotOut]:
    """Asigna a cada snapshot los flujos y cobros con fecha en (snapshot anterior, snapshot]."""
    # Sin snapshot base, el primer punto queda sin flujo pero los siguientes sí lo tienen
    events_from = (prev_date or rows[0].date) + timedelta(days=1)
    flows = net_flows(db, user_id, from_date=events_from, to_date=rows[-1].date)
    incomes = income_events(db, user_id, from_date=events_from, to_date=rows[-1].date)
    amorts = amortization_events(db, user_id, from_date=events_from, to_date=rows[-1].date)

    # Clase de cada símbolo según las tenencias registradas (misma clase que usa el gráfico)
    clase_by_sym: dict[str, str] = {}
    for r in rows:
        for h in r.breakdown_json or []:
            if h.get("simbolo") and h.get("clase"):
                clase_by_sym[h["simbolo"]] = h["clase"]
    for h in db.query(Holding).filter(Holding.user_id == user_id).all():
        clase_by_sym[h.simbolo] = h.clase

    def clase_of(event: dict) -> str:
        sym = event["simbolo"] or ""
        # Los cobros en dólares vienen como "MCD US$": la clase es la del ticker base
        base = _USD_MARKER.sub("", sym)
        return (
            clase_by_sym.get(sym)
            or clase_by_sym.get(base)
            or classify_asset(simbolo=base, descripcion=event["descripcion"])
        )

    def holding_symbol(event: dict) -> str:
        """Símbolo de la tenencia a la que corresponde un pago ("GD35 US$" o "GD35D" → "GD35")."""
        base = _USD_MARKER.sub("", event["simbolo"] or "")
        if base in clase_by_sym:
            return base
        stripped, _suffix = normalize_ticker(base)
        return stripped if stripped in clase_by_sym else base

    def by_symbol(events: list[dict], lo: date, hi: date) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for e in events:
            if lo < e["fecha"] <= hi:
                c = out.setdefault(holding_symbol(e), {"ars": 0.0, "usd": 0.0})
                c["ars"] += e["ars"]
                c["usd"] += e["usd"]
        return {k: {cur: round(v[cur], 2) for cur in v} for k, v in out.items()}

    def window_totals(events: list[dict], lo: date, hi: date):
        total = {"ars": 0.0, "usd": 0.0}
        por_clase: dict[str, dict[str, float]] = {}
        for e in events:
            if not (lo < e["fecha"] <= hi):
                continue
            c = por_clase.setdefault(clase_of(e), {"ars": 0.0, "usd": 0.0})
            for cur in ("ars", "usd"):
                total[cur] += e[cur]
                c[cur] += e[cur]
        rounded = {k: {cur: round(v[cur], 2) for cur in v} for k, v in por_clase.items()}
        return round(total["ars"], 2), round(total["usd"], 2), rounded

    # Snapshots viejos guardados sin cotización tienen USD en 0: se recalculan con el MEP de ese día
    mep = build_mep_lookup(db, rows[0].date, rows[-1].date)
    mep_dates = sorted(mep.keys())

    out = []
    for r in rows:
        snap = SnapshotOut.model_validate(r)
        _repair_usd(snap, fx_for_date(mep, mep_dates, r.date))
        if prev_date is not None:
            snap.flujo_ars, snap.flujo_usd, snap.flujo_por_clase = window_totals(flows, prev_date, r.date)
            snap.ingreso_ars, snap.ingreso_usd, snap.ingreso_por_clase = window_totals(incomes, prev_date, r.date)
            snap.amort_por_simbolo = by_symbol(amorts, prev_date, r.date)
        out.append(snap)
        prev_date = r.date
    return out


def _repair_usd(snap: SnapshotOut, mep_rate: float | None) -> None:
    rate = snap.dolar_rate or mep_rate
    if not rate:
        return
    if snap.total_usd <= 0:
        snap.total_usd = round(snap.total_ars / rate, 2)
    fixed = []
    for h in snap.breakdown_json or []:
        if isinstance(h, dict) and not h.get("valuacion_usd") and h.get("valuacion_ars"):
            h = {**h, "valuacion_usd": float(h["valuacion_ars"]) / rate}
        fixed.append(h)
    snap.breakdown_json = fixed


@router.post("/run-now", response_model=SnapshotOut | None)
async def run_now(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = await snapshot_job.run(source="manual")
    if not result:
        raise HTTPException(status_code=409, detail="No se pudo generar el snapshot (IOL no conectado, error o cartera sin valuación)")
    row = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.id == result["id"], PortfolioSnapshot.user_id == user.id)
        .first()
    )
    return row


@router.post("/reconstruct")
async def reconstruct(
    dias: int = Query(default=365, ge=7, le=3650),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Genera snapshots diarios hacia atrás a partir de las tenencias, operaciones y precios históricos."""
    try:
        # Las tenencias de hoy son el punto de partida: mejor que estén frescas
        await portfolio_service.refresh_holdings(db, user.id)
    except (IolNotConnectedError, IolAuthError):
        raise HTTPException(status_code=409, detail="IOL no está conectado")
    except Exception:
        pass  # se usan las tenencias guardadas
    try:
        return await history_service.reconstruct_snapshots(db, user.id, dias=dias)
    except IolNotConnectedError:
        raise HTTPException(status_code=409, detail="IOL no está conectado")
    except IolAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))


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
