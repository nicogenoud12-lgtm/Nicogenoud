"""Snapshots en 0: no se guardan, no se muestran, y el USD faltante se recalcula."""
import asyncio
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, DolarQuote, Holding, PortfolioSnapshot, User
from app.routers.snapshots import list_snapshots
from app.services import portfolio_service


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


@pytest.fixture()
def user(db):
    u = User(username="test", password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


def _snap(db, user, d, ars, usd, rate=1500.0, breakdown=None):
    db.add(PortfolioSnapshot(user_id=user.id, date=d, total_ars=ars, total_usd=usd, dolar_rate=rate,
                             dolar_source="MEP", source="test", breakdown_json=breakdown or []))


def test_save_snapshot_skips_empty_portfolio(db, user):
    assert portfolio_service.save_snapshot(db, user.id, dolar_rate=1500, dolar_source="MEP") is None
    assert db.query(PortfolioSnapshot).count() == 0


def test_save_snapshot_fills_usd_when_valuations_missing(db, user):
    db.add(Holding(user_id=user.id, mercado="argentina", simbolo="GGAL", clase="Acción",
                   cantidad=1, valuacion_ars=300_000, valuacion_usd=0))
    db.add(DolarQuote(date=date.today() - timedelta(days=3), source="MEP", compra=1500, venta=1500, promedio=1500))
    db.commit()

    snap = portfolio_service.save_snapshot(db, user.id, dolar_rate=0, dolar_source="MEP")

    assert float(snap.dolar_rate) == 1500
    assert float(snap.total_usd) == pytest.approx(200)


def test_list_hides_zero_and_repairs_usd(db, user):
    today = date.today()
    _snap(db, user, today - timedelta(days=2), 3_000_000, 2000)
    _snap(db, user, today - timedelta(days=1), 0, 0)                      # IOL falló
    _snap(db, user, today, 3_030_000, 0, rate=0,                           # sin cotización
          breakdown=[{"simbolo": "GGAL", "clase": "Acción", "valuacion_ars": 3_030_000, "valuacion_usd": 0}])
    db.add(DolarQuote(date=today, source="MEP", compra=1515, venta=1515, promedio=1515))
    db.commit()

    out = list_snapshots(days=30, user=user, db=db)

    assert [s.date for s in out] == [today - timedelta(days=2), today]
    assert out[1].total_usd == pytest.approx(2000)
    assert out[1].breakdown_json[0]["valuacion_usd"] == pytest.approx(2000)


class _EmptyClient:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_portafolio(self, pais):
        return {"activos": []}


def test_refresh_ignores_empty_portfolio_when_holdings_exist(db, user, monkeypatch):
    db.add(DolarQuote(date=date.today(), source="MEP", compra=1500, venta=1500, promedio=1500))
    db.add(Holding(user_id=user.id, mercado="argentina", simbolo="GGAL", clase="Acción",
                   cantidad=5, valuacion_ars=30_000, valuacion_usd=20))
    db.commit()
    monkeypatch.setattr(portfolio_service, "IolClient", _EmptyClient)

    asyncio.run(portfolio_service.refresh_holdings(db, user.id))

    assert [h.simbolo for h in db.query(Holding).all()] == ["GGAL"]
