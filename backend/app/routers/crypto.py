from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import CryptoHolding, CryptoSnapshot, User
from ..schemas import (
    CoinSearchResult,
    CryptoHoldingIn,
    CryptoHoldingOut,
    CryptoReport,
    CryptoSnapshotOut,
)
from ..services import coingecko, crypto_service
from ..services.coingecko import CoinGeckoError

router = APIRouter(prefix="/crypto", tags=["crypto"])


def _apply(holding: CryptoHolding, data: CryptoHoldingIn) -> None:
    holding.symbol = data.symbol.strip().upper()
    holding.name = (data.name or None) and data.name.strip()
    holding.coingecko_id = (data.coingecko_id or None) and data.coingecko_id.strip().lower()
    holding.cantidad = float(data.cantidad)
    holding.costo_usd_unit = float(data.costo_usd_unit) if data.costo_usd_unit is not None else None
    holding.exchange = (data.exchange or None) and data.exchange.strip()
    holding.notas = (data.notas or None) and data.notas.strip()


@router.get("/holdings", response_model=list[CryptoHoldingOut])
def list_holdings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(CryptoHolding)
        .filter(CryptoHolding.user_id == user.id)
        .order_by(CryptoHolding.symbol.asc(), CryptoHolding.id.asc())
        .all()
    )


@router.post("/holdings", response_model=CryptoHoldingOut, status_code=201)
def create_holding(
    body: CryptoHoldingIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    h = CryptoHolding(user_id=user.id, symbol="", cantidad=0)
    _apply(h, body)
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


@router.put("/holdings/{holding_id}", response_model=CryptoHoldingOut)
def update_holding(
    holding_id: int,
    body: CryptoHoldingIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    h = (
        db.query(CryptoHolding)
        .filter(CryptoHolding.id == holding_id, CryptoHolding.user_id == user.id)
        .first()
    )
    if h is None:
        raise HTTPException(status_code=404, detail="Holding not found")
    _apply(h, body)
    db.commit()
    db.refresh(h)
    return h


@router.delete("/holdings/{holding_id}", status_code=204)
def delete_holding(
    holding_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    h = (
        db.query(CryptoHolding)
        .filter(CryptoHolding.id == holding_id, CryptoHolding.user_id == user.id)
        .first()
    )
    if h is None:
        raise HTTPException(status_code=404, detail="Holding not found")
    db.delete(h)
    db.commit()
    return None


@router.get("/search", response_model=list[CoinSearchResult])
async def search_coins(
    q: str = Query(..., min_length=1, max_length=64),
    _user: User = Depends(get_current_user),
):
    try:
        return await coingecko.search(q)
    except CoinGeckoError as e:
        raise HTTPException(status_code=502, detail=f"CoinGecko: {e}")


@router.get("/report", response_model=CryptoReport)
async def report(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await crypto_service.build_report_and_snapshot(db, user.id)


@router.get("/snapshots", response_model=list[CryptoSnapshotOut])
def list_snapshots(
    days: int = Query(default=180, ge=1, le=3650),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    since = date.today() - timedelta(days=days)
    return (
        db.query(CryptoSnapshot)
        .filter(CryptoSnapshot.user_id == user.id, CryptoSnapshot.date >= since)
        .order_by(CryptoSnapshot.date.asc())
        .all()
    )
