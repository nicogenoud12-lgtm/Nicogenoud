"""Tests for portfolio_service: refresh_holdings resiliency + unrealized P&L currency."""
import asyncio
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, DolarQuote, Holding, User
from app.services import portfolio_service


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture()
def user(db):
    u = User(username="test", password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


class _FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_portafolio(self, pais):
        if pais == "estados_unidos":
            raise RuntimeError("IOL 500")
        return {"activos": [{
            "titulo": {"simbolo": "GGAL", "tipo": "ACCIONES", "moneda": "peso_Argentino"},
            "cantidad": 5, "valorizado": 30000, "variacion": 1.2,
        }]}


def test_refresh_keeps_holdings_of_failed_market(db, user, monkeypatch):
    db.add(DolarQuote(date=date.today(), source="MEP", compra=1500, venta=1500, promedio=1500))
    db.add(Holding(user_id=user.id, mercado="estados_unidos", simbolo="SPY",
                   clase="CEDEAR", cantidad=1, valuacion_ars=900000, valuacion_usd=600))
    db.add(Holding(user_id=user.id, mercado="argentina", simbolo="VENDIDA",
                   clase="Acción", cantidad=1, valuacion_ars=1, valuacion_usd=0))
    db.commit()
    monkeypatch.setattr(portfolio_service, "IolClient", _FakeClient)

    asyncio.run(portfolio_service.refresh_holdings(db, user.id))

    simbolos = {(h.mercado, h.simbolo) for h in db.query(Holding).all()}
    # SPY se conserva porque estados_unidos falló; VENDIDA se borra porque argentina respondió
    assert simbolos == {("estados_unidos", "SPY"), ("argentina", "GGAL")}


def test_pnl_no_realizada_respects_holding_currency(db, user):
    db.add(Holding(user_id=user.id, mercado="argentina", simbolo="GGAL", clase="Acción",
                   cantidad=1, valuacion_ars=0, valuacion_usd=0,
                   ganancia_dinero=150_000, moneda="peso_Argentino"))
    db.add(Holding(user_id=user.id, mercado="estados_unidos", simbolo="SPY", clase="CEDEAR",
                   cantidad=1, valuacion_ars=0, valuacion_usd=0,
                   ganancia_dinero=100, moneda="dolar_Estadounidense"))
    db.commit()

    k = portfolio_service.compute_kpis(db, user.id, dolar_rate=1500, dolar_source="MEP")

    assert k["pnl_no_realizada_ars"] == pytest.approx(150_000 + 100 * 1500)
    assert k["pnl_no_realizada_usd"] == pytest.approx(100 + 100)
