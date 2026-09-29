"""Datos que alimentan el rendimiento: monto de compras de bonos y cobros por tramo."""
import asyncio
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, DolarQuote, Operation, PortfolioSnapshot, User
from app.routers.snapshots import _with_flows
from app.services import operations_service


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
    db.add(DolarQuote(date=date(2026, 7, 1), source="MEP", compra=1500, venta=1500, promedio=1500))
    db.commit()
    return u


def _fake_client(ops):
    class _C:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get_operaciones(self, **kw):
            return ops

        async def get_movimientos(self, **kw):
            return []

    return _C


@pytest.mark.parametrize(
    "monto,expected",
    [
        (851_700, -851_700),       # monto con comisiones (+0,4%): se usa monto
        (85_150_000, -848_300),    # monto sobre valor nominal (≈100×): se ignora
    ],
)
def test_compra_bono_monto_only_when_fee_sized(db, user, monkeypatch, monto, expected):
    op = {"numero": 1, "tipo": "Compra", "simbolo": "TZXS7", "fechaOperada": "2026-07-16",
          "cantidadOperada": 783_365, "precioOperado": 108.29, "montoOperado": 848_300, "monto": monto}
    monkeypatch.setattr(operations_service, "IolClient", _fake_client([op]))

    async def no_backfill(*a, **k):
        return 0

    monkeypatch.setattr(operations_service, "backfill_historical_mep", no_backfill)
    asyncio.run(operations_service.sync_operations(db, user.id, year=2026, hasta=date(2026, 7, 31)))

    assert float(db.query(Operation).one().monto_neto) == pytest.approx(expected)


def test_snapshot_income_window_and_usd_marker_class(db, user):
    bd = [{"simbolo": "MCD", "clase": "CEDEAR"}, {"simbolo": "GD35", "clase": "Bono"}]
    rows = []
    for d in (date(2026, 7, 1), date(2026, 7, 2)):
        row = PortfolioSnapshot(user_id=user.id, date=d, total_ars=1e7, total_usd=1e7 / 1500, dolar_rate=1500,
                                dolar_source="MEP", source="t", breakdown_json=bd)
        db.add(row)
        rows.append(row)
    for n, kind, sym, amt in (("1", "DIVIDENDO", "MCD US$", 3.0), ("2", "RENTA", "GD35 US$", 40.0),
                              ("3", "AMORTIZACION", "GD35D", 25.0)):
        db.add(Operation(user_id=user.id, iol_numero=n, fecha_operada=date(2026, 7, 2), event_kind=kind,
                         currency_kind="USD_MEP", monto_neto=amt, simbolo=sym))
    db.commit()

    out = _with_flows(db, user.id, rows, date(2026, 6, 30))

    assert out[1].ingreso_usd == pytest.approx(43)
    assert out[1].ingreso_por_clase == {"CEDEAR": {"ars": 4500, "usd": 3}, "Bono": {"ars": 60000, "usd": 40}}
    # La amortización va por símbolo de la tenencia (GD35D → GD35), no como ingreso general
    assert out[1].amort_por_simbolo == {"GD35": {"ars": 37500, "usd": 25}}
    assert out[1].flujo_usd == pytest.approx(-25)  # sigue siendo retiro para el cálculo por flujos
