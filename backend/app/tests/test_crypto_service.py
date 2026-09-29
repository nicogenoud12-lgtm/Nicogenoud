"""Tests for crypto_service: snapshot ante falla parcial, backfill sin pisar,
flujos para el gráfico y P&L realizado en ARS."""
import asyncio
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, CryptoHolding, CryptoSale, CryptoSnapshot, User
from app.schemas import CryptoSaleOut, CryptoSnapshotOut
from app.services import binance as binance_svc
from app.services import coingecko, crypto_service


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


@pytest.fixture()
def fixed_rate(monkeypatch):
    async def fake_rate(_db):
        return 1000.0, "MEP"

    monkeypatch.setattr(crypto_service, "_get_dolar_rate", fake_rate)


def _snap(db, user, d, total_usd, cost_usd, rate=1000.0):
    s = CryptoSnapshot(
        user_id=user.id, date=d, total_usd=total_usd, total_ars=total_usd * rate,
        cost_usd=cost_usd, dolar_rate=rate, breakdown_json=[],
    )
    db.add(s)
    db.commit()
    return s


def _sale(db, user, symbol, cid, qty, sold_at, cost_total=None, pnl=None, proceeds=0.0, rate=1000.0):
    s = CryptoSale(
        user_id=user.id, symbol=symbol, coingecko_id=cid, cantidad=qty,
        costo_usd_unit=(cost_total / qty) if cost_total is not None else None,
        price_usd=proceeds / qty, proceeds_usd=proceeds, cost_total_usd=cost_total,
        pnl_usd=pnl, dolar_rate=rate, sold_at=sold_at,
    )
    db.add(s)
    db.commit()
    return s


# ---------------------------------------------------------------- item 1 ---

def _patch_prices(monkeypatch, prices: dict):
    async def fake_binance(ids):
        return {k: v for k, v in prices.items() if k in ids}

    async def fake_cg(ids, **_kw):
        return {}

    async def fake_7d(ids):
        return {}

    monkeypatch.setattr(binance_svc, "get_prices", fake_binance)
    monkeypatch.setattr(binance_svc, "get_7d_changes", fake_7d)
    monkeypatch.setattr(coingecko, "get_prices", fake_cg)


def test_partial_price_failure_keeps_last_snapshot(db, user, monkeypatch, fixed_rate):
    db.add(CryptoHolding(user_id=user.id, symbol="BTC", coingecko_id="bitcoin", cantidad=1, costo_usd_unit=50000))
    db.add(CryptoHolding(user_id=user.id, symbol="ETH", coingecko_id="ethereum", cantidad=10, costo_usd_unit=2000))
    db.commit()
    _snap(db, user, date.today(), total_usd=90000, cost_usd=70000)

    # Sólo llega el precio de BTC: el total saldría subvaluado.
    _patch_prices(monkeypatch, {"bitcoin": {"usd": 60000.0}})
    report = asyncio.run(crypto_service.build_report_and_snapshot(db, user.id))
    assert report["total_value_usd"] == 60000.0

    row = db.query(CryptoSnapshot).filter_by(user_id=user.id, date=date.today()).one()
    assert float(row.total_usd) == 90000


def test_complete_prices_update_snapshot(db, user, monkeypatch, fixed_rate):
    db.add(CryptoHolding(user_id=user.id, symbol="BTC", coingecko_id="bitcoin", cantidad=1, costo_usd_unit=50000))
    # Sin coingecko_id ni símbolo conocido: nunca se valúa, no bloquea el snapshot.
    db.add(CryptoHolding(user_id=user.id, symbol="ZZZNOPE", coingecko_id=None, cantidad=5))
    db.commit()
    _snap(db, user, date.today(), total_usd=90000, cost_usd=70000)

    _patch_prices(monkeypatch, {"bitcoin": {"usd": 60000.0}})
    asyncio.run(crypto_service.build_report_and_snapshot(db, user.id))

    row = db.query(CryptoSnapshot).filter_by(user_id=user.id, date=date.today()).one()
    assert float(row.total_usd) == 60000
    assert float(row.cost_usd) == 50000


# ---------------------------------------------------------------- item 2 ---

def _patch_history(monkeypatch, histories: dict):
    async def fake_hist(cid, since, until):
        daily = histories.get(cid)
        if daily is None:
            return {}
        out, cur = {}, since
        while cur <= until:
            out[cur] = daily
            cur += timedelta(days=1)
        return out

    async def fake_cg_hist(cid, since, until):
        return {}

    async def no_sleep(_s):
        return None

    monkeypatch.setattr(binance_svc, "fetch_history_usd", fake_hist)
    monkeypatch.setattr(coingecko, "fetch_history_usd", fake_cg_hist)
    monkeypatch.setattr(crypto_service.asyncio, "sleep", no_sleep)


def test_backfill_reconstructs_quantities_and_never_overwrites(db, user, monkeypatch, fixed_rate):
    # Hoy: 1 BTC a costo 100. Se vendieron 0.5 BTC el 3/1 y todo el ETH (2) el 2/1.
    db.add(CryptoHolding(user_id=user.id, symbol="BTC", coingecko_id="bitcoin", cantidad=1, costo_usd_unit=100))
    db.commit()
    _sale(db, user, "BTC", "bitcoin", 0.5, datetime(2026, 1, 3, 12, 0), cost_total=50, pnl=10, proceeds=60)
    _sale(db, user, "ETH", "ethereum", 2, datetime(2026, 1, 2, 12, 0), cost_total=20, pnl=0, proceeds=20)
    existing = _snap(db, user, date(2026, 1, 2), total_usd=999, cost_usd=888)

    _patch_history(monkeypatch, {"bitcoin": 100.0, "ethereum": 10.0})
    res = asyncio.run(
        crypto_service.backfill_history(db, user.id, since=date(2026, 1, 1), until=date(2026, 1, 4))
    )
    assert res["days"] == 3
    assert res["skipped_existing"] == 1

    rows = {
        r.date: r for r in db.query(CryptoSnapshot).filter_by(user_id=user.id).all()
    }
    # 1/1: 1.5 BTC + 2 ETH; costo 100 + 50 (BTC vendido) + 20 (ETH vendido)
    assert float(rows[date(2026, 1, 1)].total_usd) == pytest.approx(170)
    assert float(rows[date(2026, 1, 1)].cost_usd) == pytest.approx(170)
    assert float(rows[date(2026, 1, 1)].total_ars) == pytest.approx(170_000)
    # 2/1 existía: no se toca
    assert rows[date(2026, 1, 2)].id == existing.id
    assert float(rows[date(2026, 1, 2)].total_usd) == 999
    assert float(rows[date(2026, 1, 2)].cost_usd) == 888
    # 3/1 en adelante: la venta de ese día ya está descontada
    assert float(rows[date(2026, 1, 3)].total_usd) == pytest.approx(100)
    assert float(rows[date(2026, 1, 3)].cost_usd) == pytest.approx(100)
    assert float(rows[date(2026, 1, 4)].total_usd) == pytest.approx(100)


def test_backfill_skips_days_with_missing_history(db, user, monkeypatch, fixed_rate):
    db.add(CryptoHolding(user_id=user.id, symbol="BTC", coingecko_id="bitcoin", cantidad=1, costo_usd_unit=100))
    db.commit()
    # ETH vendido el 2/1 sin historial de precios: 1/1 quedaría incompleto.
    _sale(db, user, "ETH", "ethereum", 2, datetime(2026, 1, 2, 12, 0), cost_total=20, pnl=0, proceeds=20)

    _patch_history(monkeypatch, {"bitcoin": 100.0})
    res = asyncio.run(
        crypto_service.backfill_history(db, user.id, since=date(2026, 1, 1), until=date(2026, 1, 3))
    )
    dates = {r.date for r in db.query(CryptoSnapshot).filter_by(user_id=user.id).all()}
    assert date(2026, 1, 1) not in dates
    assert dates == {date(2026, 1, 2), date(2026, 1, 3)}
    assert res["skipped_incomplete"] == 1
    assert "ETH" in res["failed_symbols"]


def test_backfill_noop_when_all_dates_exist(db, user, monkeypatch, fixed_rate):
    db.add(CryptoHolding(user_id=user.id, symbol="BTC", coingecko_id="bitcoin", cantidad=1))
    db.commit()
    _snap(db, user, date(2026, 1, 1), total_usd=5, cost_usd=0)

    async def boom(*_a, **_kw):
        raise AssertionError("no debería pedir historial")

    monkeypatch.setattr(binance_svc, "fetch_history_usd", boom)
    res = asyncio.run(
        crypto_service.backfill_history(db, user.id, since=date(2026, 1, 1), until=date(2026, 1, 1))
    )
    assert res["days"] == 0
    assert res["skipped_existing"] == 1


# ---------------------------------------------------------------- item 6 ---

def test_snapshot_flows(db, user):
    _snap(db, user, date(2026, 3, 1), total_usd=1000, cost_usd=800, rate=1000)
    # Compra de 500 USD: el costo sube 500.
    _snap(db, user, date(2026, 3, 2), total_usd=1550, cost_usd=1300, rate=1100)
    # Venta con base 300 y P&L +50 (cobró 350): costo baja 300, flujo = -350.
    _sale(db, user, "BTC", "bitcoin", 1, datetime(2026, 3, 3, 12, 0), cost_total=300, pnl=50, proceeds=350)
    _snap(db, user, date(2026, 3, 3), total_usd=1200, cost_usd=1000, rate=0)
    # Venta de algo sin costo conocido (cobró 40): costo no cambia, flujo = -40.
    _sale(db, user, "XYZ", None, 1, datetime(2026, 3, 4, 12, 0), cost_total=None, pnl=None, proceeds=40)
    _snap(db, user, date(2026, 3, 4), total_usd=1170, cost_usd=1000, rate=1200)

    rows = crypto_service.snapshots_with_flows(db, user.id, date(2026, 1, 1))
    assert [r["flujo_usd"] for r in rows] == [0.0, 500.0, -350.0, -40.0]
    assert rows[0]["flujo_ars"] == 0.0
    assert rows[1]["flujo_ars"] == pytest.approx(550_000)
    assert rows[2]["flujo_ars"] is None  # snapshot sin cotización
    assert rows[3]["flujo_ars"] == pytest.approx(-48_000)

    out = [CryptoSnapshotOut.model_validate(r) for r in rows]
    assert out[1].flujo_usd == 500.0
    assert out[0].taken_at.tzinfo is not None


def test_snapshot_flows_window_starts_at_zero(db, user):
    _snap(db, user, date(2026, 3, 1), total_usd=1000, cost_usd=800)
    _snap(db, user, date(2026, 3, 5), total_usd=1500, cost_usd=1300)
    rows = crypto_service.snapshots_with_flows(db, user.id, date(2026, 3, 2))
    assert len(rows) == 1
    assert rows[0]["flujo_usd"] == 0.0


# ------------------------------------------------------------ items 3/4 ---

def test_sales_report_pnl_ars_uses_each_sale_rate(db, user):
    _sale(db, user, "BTC", "bitcoin", 1, datetime(2026, 2, 1, 12), cost_total=100, pnl=10, proceeds=110, rate=1000)
    _sale(db, user, "ETH", "ethereum", 1, datetime(2026, 3, 1, 12), cost_total=100, pnl=-5, proceeds=95, rate=1200)
    # Venta vieja sin cotización guardada: usa la actual.
    _sale(db, user, "SOL", "solana", 1, datetime(2026, 4, 1, 12), cost_total=100, pnl=2, proceeds=102, rate=0)
    rep = crypto_service.sales_report(db, user.id, ars_rate=1500.0, dolar_source="MEP")
    assert rep["total_pnl_usd"] == pytest.approx(7)
    assert rep["total_pnl_ars"] == pytest.approx(10 * 1000 - 5 * 1200 + 2 * 1500)


def test_sold_at_serialized_as_utc(db, user):
    # 22:30 ART del 28/9 = 01:30 UTC del 29/9; SQLite lo devuelve naive.
    s = _sale(db, user, "BTC", "bitcoin", 1, datetime(2026, 9, 29, 1, 30), cost_total=1, pnl=0, proceeds=1)
    db.expire_all()
    s = db.get(CryptoSale, s.id)
    assert s.sold_at.tzinfo is None
    js = CryptoSaleOut.model_validate(s).model_dump(mode="json")
    assert js["sold_at"] == "2026-09-29T01:30:00Z"
