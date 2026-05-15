from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import CryptoHolding, User
from ..schemas import CryptoHoldingIn, CryptoHoldingOut

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
