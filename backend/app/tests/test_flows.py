"""Flujos netos para la variación diaria del gráfico de evolución."""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, DolarQuote, Operation, PortfolioSnapshot, User
from app.routers.snapshots import _with_flows
from app.services.pnl import net_flows, operations_summary


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
    db.add(DolarQuote(date=date(2026, 9, 1), source="MEP", compra=1500, venta=1500, promedio=1500))
    db.commit()
    return u


def _op(db, user, numero, fecha, kind, monto, cur="ARS", simbolo="GGAL"):
    db.add(Operation(user_id=user.id, iol_numero=numero, fecha_operada=fecha,
                     event_kind=kind, currency_kind=cur, monto_neto=monto, simbolo=simbolo))


def _snap(db, user, d, total_ars, breakdown=None):
    row = PortfolioSnapshot(user_id=user.id, date=d, total_ars=total_ars, total_usd=total_ars / 1500,
                            dolar_rate=1500, dolar_source="MEP", source="test",
                            breakdown_json=breakdown or [])
    db.add(row)
    return row


def test_net_flows_signs_and_excludes_income(db, user):
    _op(db, user, "1", date(2026, 9, 2), "COMPRA", -1_500_000)
    _op(db, user, "2", date(2026, 9, 2), "AMORTIZACION", 100, cur="USD_MEP", simbolo="GD35")
    _op(db, user, "3", date(2026, 9, 2), "RENTA", 50, cur="USD_MEP", simbolo="GD35")
    _op(db, user, "4", date(2026, 9, 2), "DIVIDENDO", 10, cur="USD_MEP", simbolo="KO")
    db.commit()

    flows = net_flows(db, user.id, from_date=date(2026, 9, 1), to_date=date(2026, 9, 30))

    assert sorted((f["simbolo"], f["ars"]) for f in flows) == [
        ("GD35", pytest.approx(-150_000)),
        ("GGAL", pytest.approx(1_500_000)),
    ]


def test_snapshot_flows_assigned_to_window_and_class(db, user):
    bd = [{"simbolo": "GGAL", "clase": "Acción"}, {"simbolo": "GD35", "clase": "Bono"}]
    rows = [_snap(db, user, date(2026, 9, 1), 10_000_000, bd),
            _snap(db, user, date(2026, 9, 3), 11_600_000, bd)]
    _op(db, user, "1", date(2026, 9, 2), "COMPRA", -1_500_000)          # entre ambos snapshots
    _op(db, user, "2", date(2026, 9, 1), "COMPRA", -700_000)            # ya en el snapshot base
    _op(db, user, "3", date(2026, 9, 3), "AMORTIZACION", 100, cur="USD_MEP", simbolo="GD35")
    db.commit()

    out = _with_flows(db, user.id, rows, date(2026, 8, 31))

    assert out[0].flujo_ars == pytest.approx(700_000)
    assert out[1].flujo_ars == pytest.approx(1_500_000 - 150_000)
    assert out[1].flujo_por_clase == {
        "Acción": {"ars": 1_500_000, "usd": 1000},
        "Bono": {"ars": -150_000, "usd": -100},
    }
    # Rendimiento real del día: 11.6M − 10M − 1.35M = +250k
    assert (11_600_000 - 10_000_000 - out[1].flujo_ars) == pytest.approx(250_000)


def test_snapshot_without_base_has_no_flows(db, user):
    rows = [_snap(db, user, date(2026, 9, 1), 10_000_000)]
    _op(db, user, "1", date(2026, 9, 1), "COMPRA", -1_500_000)
    db.commit()

    assert _with_flows(db, user.id, rows, None)[0].flujo_ars == 0


def test_summary_by_simbolo_includes_income(db, user):
    _op(db, user, "1", date(2026, 9, 2), "RENTA", 50, cur="USD_MEP", simbolo="GD35")
    _op(db, user, "2", date(2026, 9, 3), "AMORTIZACION", 100, cur="USD_MEP", simbolo="GD35")
    db.commit()

    s = operations_summary(db, user.id, from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
    gd35 = next(x for x in s["by_simbolo"] if x["simbolo"] == "GD35")

    assert gd35["renta_usd"] == 50
    assert gd35["amortizaciones_ars"] == 150_000
