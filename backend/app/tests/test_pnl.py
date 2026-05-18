"""Tests for pnl.operations_summary — bidirectional FX conversion."""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, DolarQuote, Operation, User
from app.services.pnl import operations_summary


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


def test_converts_to_both_currencies(db, user):
    db.add(DolarQuote(date=date(2026, 3, 1), source="MEP", compra=1490, venta=1510, promedio=1500))
    db.add(DolarQuote(date=date(2026, 4, 1), source="MEP", compra=1590, venta=1610, promedio=1600))
    # ARS renta: 150.000 pesos
    db.add(Operation(
        user_id=user.id, iol_numero="1",
        fecha_operada=date(2026, 3, 1),
        event_kind="RENTA", currency_kind="ARS",
        monto_neto=150_000,
    ))
    # USD renta: 100 USD
    db.add(Operation(
        user_id=user.id, iol_numero="2",
        fecha_operada=date(2026, 4, 1),
        event_kind="RENTA", currency_kind="USD_MEP",
        monto_neto=100,
    ))
    db.commit()

    s = operations_summary(db, user.id, year=2026)

    # ARS total: 150.000 (nativa) + 100 × 1600 = 310.000
    assert s["total_renta_ars"] == 310_000.00
    # USD total: 150.000 / 1500 + 100 = 200
    assert s["total_renta_usd"] == 200.00
    assert s["fx_missing_count"] == 0


def test_missing_fx_uses_native_currency_only(db, user):
    # No DolarQuote rows — no MEP available
    db.add(Operation(
        user_id=user.id, iol_numero="3",
        fecha_operada=date(2026, 5, 1),
        event_kind="DIVIDENDO", currency_kind="USD_MEP",
        monto_neto=50,
    ))
    db.commit()

    s = operations_summary(db, user.id, year=2026)

    assert s["fx_missing_count"] == 1
    assert s["total_dividendos_usd"] == 50.00
    # Without a rate, the USD op contributes 0 to the ARS bucket — no artificial inflation
    assert s["total_dividendos_ars"] == 0.00


def test_fallback_to_nearest_date(db, user):
    # Rate exists for 2026-03-02, not for 2026-03-01
    db.add(DolarQuote(date=date(2026, 3, 2), source="MEP", compra=1490, venta=1510, promedio=1500))
    db.add(Operation(
        user_id=user.id, iol_numero="4",
        fecha_operada=date(2026, 3, 1),
        event_kind="COMPRA", currency_kind="USD_MEP",
        monto_neto=200,
    ))
    db.commit()

    s = operations_summary(db, user.id, year=2026)

    # Falls back to 2026-03-02 rate (nearest next date)
    assert s["total_compras_ars"] == 200 * 1500
    assert s["fx_missing_count"] == 0


def test_amortizacion_counts_in_renta_bucket(db, user):
    db.add(DolarQuote(date=date(2026, 2, 1), source="MEP", compra=1490, venta=1510, promedio=1500))
    db.add(Operation(
        user_id=user.id, iol_numero="5",
        fecha_operada=date(2026, 2, 1),
        event_kind="AMORTIZACION", currency_kind="USD_MEP",
        monto_neto=300,
    ))
    db.commit()

    s = operations_summary(db, user.id, year=2026)

    assert s["total_renta_usd"] == 300.00
    assert s["total_renta_ars"] == 300 * 1500


def test_by_mes_contains_both_currencies(db, user):
    db.add(DolarQuote(date=date(2026, 1, 5), source="MEP", compra=1490, venta=1510, promedio=1500))
    db.add(Operation(
        user_id=user.id, iol_numero="6",
        fecha_operada=date(2026, 1, 5),
        event_kind="COMPRA", currency_kind="ARS",
        monto_neto=30_000,
    ))
    db.commit()

    s = operations_summary(db, user.id, year=2026)
    mes1 = next(m for m in s["by_mes"] if m["mes"] == 1)

    assert mes1["compras_ars"] == 30_000.00
    assert abs(mes1["compras_usd"] - 30_000 / 1500) < 0.01
