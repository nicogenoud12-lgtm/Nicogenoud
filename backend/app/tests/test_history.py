"""Reconstrucción de la evolución diaria a partir de tenencias, operaciones y precios."""
import asyncio
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, DolarQuote, Holding, Operation, PortfolioSnapshot, User
from app.services import history_service

TODAY = date.today()


def _d(days_ago):
    return TODAY - timedelta(days=days_ago)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


@pytest.fixture()
def user(db):
    u = User(username="papa", password_hash="x", is_admin=False)
    db.add(u)
    for i in range(0, 80):
        db.add(DolarQuote(date=_d(i), source="MEP", compra=1000, venta=1000, promedio=1000))
    db.commit()
    return u


def _series(prices_by_days_ago):
    return [{"ultimoPrecio": p, "fechaHora": f"{_d(n).isoformat()}T17:00:00"} for n, p in prices_by_days_ago.items()]


@pytest.fixture()
def run(db, user, monkeypatch):
    series = {
        # Bono: cotiza cada 100 VN
        "AL30": _series({n: (85_000 if n < 10 else 80_000) for n in range(0, 25)}),
        # Acción vendida hace 5 días: ya no está en la cartera
        "GGAL": _series({n: 5_000 for n in range(0, 25)}),
    }

    class _C:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get_serie_historica(self, mercado, simbolo, **kw):
            if simbolo not in series:
                raise RuntimeError("404")
            return series[simbolo]

    async def no_backfill(*a, **k):
        return 0

    monkeypatch.setattr(history_service, "IolClient", _C)
    monkeypatch.setattr(history_service, "backfill_historical_mep", no_backfill)

    db.add_all([
        Holding(user_id=user.id, mercado="argentina", simbolo="AL30", clase="Bono", cantidad=1000,
                valuacion_ars=850_000, valuacion_usd=850, moneda="peso_Argentino"),
        Holding(user_id=user.id, mercado="argentina", simbolo="IOLPORA", clase="FCI", cantidad=100,
                valuacion_ars=200_000, valuacion_usd=200, moneda="peso_Argentino"),
        # Compra en dólares del mismo bono: suma a la tenencia AL30
        Operation(user_id=user.id, iol_numero="1", fecha_operada=_d(10), event_kind="COMPRA", simbolo="AL30D",
                  currency_kind="USD_MEP", cantidad=400, precio=60, monto_operado=240, monto_neto=-240),
        Operation(user_id=user.id, iol_numero="2", fecha_operada=_d(5), event_kind="VENTA", simbolo="GGAL",
                  currency_kind="ARS", cantidad=10, precio=5_000, monto_operado=50_000, monto_neto=50_000),
        Operation(user_id=user.id, iol_numero="3", fecha_operada=_d(3), event_kind="SUSCRIPCION",
                  simbolo="IOLPORA", currency_kind="ARS", cantidad=50_000, monto_operado=50_000,
                  monto_neto=-50_000),
    ])
    db.commit()
    return lambda: asyncio.run(history_service.reconstruct_snapshots(db, user.id, dias=20))


def _snap(db, days_ago):
    return db.query(PortfolioSnapshot).filter(PortfolioSnapshot.date == _d(days_ago)).one()


def _by_sym(snap):
    return {r["simbolo"]: r for r in snap.breakdown_json}


def test_reconstructs_quantities_and_values(db, run):
    res = run()
    assert res["creados"] > 0

    # Ayer: todo como hoy salvo que GGAL ya se vendió
    ayer = _by_sym(_snap(db, 1))
    assert ayer["AL30"]["cantidad"] == pytest.approx(1000)
    assert ayer["AL30"]["valuacion_ars"] == pytest.approx(850_000)
    assert "GGAL" not in ayer
    assert ayer["IOLPORA"]["valuacion_ars"] == pytest.approx(200_000)

    # Hace 15 días: antes de la compra de bonos, de la venta de GGAL y de la suscripción
    antes = _by_sym(_snap(db, 15))
    assert antes["AL30"]["cantidad"] == pytest.approx(600)
    assert antes["AL30"]["valuacion_ars"] == pytest.approx(600 * 80_000 * 0.01)
    assert antes["GGAL"]["cantidad"] == pytest.approx(10)
    assert antes["GGAL"]["valuacion_ars"] == pytest.approx(50_000)
    assert antes["IOLPORA"]["valuacion_ars"] == pytest.approx(150_000)
    snap = _snap(db, 15)
    assert float(snap.total_usd) == pytest.approx(float(snap.total_ars) / 1000)
    assert snap.source == "reconstruido"
    assert res["sin_serie"] == ["IOLPORA"]


def test_never_overwrites_real_snapshots_and_is_rerunnable(db, user, run):
    db.add(PortfolioSnapshot(user_id=user.id, date=_d(2), total_ars=1, total_usd=1, dolar_rate=1000,
                             dolar_source="MEP", source="scheduler", breakdown_json=[]))
    db.commit()
    first = run()
    assert float(_snap(db, 2).total_ars) == 1
    again = run()
    assert again["creados"] == 0
    assert again["actualizados"] == first["creados"]


def test_licitacion_new_listing_and_matured_bond(db, user, monkeypatch):
    series = {
        # ON reabierta: cotiza todo el período
        "YM43O": _series({n: 150_000 for n in range(0, 25)}),
        # ON emitida hace 8 días: antes no existía
        "OTS6O": _series({n: 160_000 for n in range(0, 9)}),
        # Bono que venció hace 12 días (ya no está en la cartera)
        "TZX26": _series({n: 200 for n in range(12, 60)}),
    }

    class _C:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get_serie_historica(self, mercado, simbolo, **kw):
            if simbolo not in series:
                raise RuntimeError("404")
            return series[simbolo]

    async def no_backfill(*a, **k):
        return 0

    monkeypatch.setattr(history_service, "IolClient", _C)
    monkeypatch.setattr(history_service, "backfill_historical_mep", no_backfill)
    db.add_all([
        Holding(user_id=user.id, mercado="argentina", simbolo="YM43O", clase="ON", cantidad=14_000,
                valuacion_ars=21_000_000, valuacion_usd=21_000, moneda="peso_Argentino",
                descripcion="On Ypf S. A. Cl.43 Vto. 14/04/30 Usd"),
        Holding(user_id=user.id, mercado="argentina", simbolo="YM39O", clase="ON", cantidad=1_000,
                valuacion_ars=1_500_000, valuacion_usd=1_500, moneda="peso_Argentino",
                descripcion="On Ypf Clase 39 Vto 22/07/30 U$S Cg"),
        Holding(user_id=user.id, mercado="argentina", simbolo="OTS6O", clase="ON", cantidad=10_000,
                valuacion_ars=16_000_000, valuacion_usd=16_000, moneda="peso_Argentino",
                descripcion="On Otamerica Ebytem S.6 29/07/29 Usd"),
        # Licitación informada como "Otro" con un nombre que no es ticker
        Operation(user_id=user.id, iol_numero="10", fecha_operada=_d(5), event_kind="OTRO",
                  simbolo="YPF CL.43 ADICIONAL", currency_kind="ARS", cantidad=14_000, precio=100,
                  monto_operado=14_000, monto_neto=14_000),
        # Amortización final del bono vencido
        Operation(user_id=user.id, iol_numero="11", fecha_operada=_d(12), event_kind="AMORTIZACION",
                  simbolo="TZX26", currency_kind="ARS", monto_operado=6_000_000, monto_neto=6_000_000),
    ])
    db.commit()
    asyncio.run(history_service.reconstruct_snapshots(db, user.id, dias=60))

    hace3 = _by_sym(_snap(db, 3))
    assert hace3["YM43O"]["cantidad"] == pytest.approx(14_000)
    assert hace3["OTS6O"]["valuacion_ars"] == pytest.approx(16_000_000)
    assert "TZX26" not in hace3

    hace15 = _by_sym(_snap(db, 15))
    assert "YM43O" not in hace15  # antes de la licitación no estaba
    assert "OTS6O" not in hace15  # antes de emitirse no existía
    assert hace15["YM39O"]["cantidad"] == pytest.approx(1_000)  # otra ON de YPF no se toca
    assert hace15["TZX26"]["valuacion_ars"] == pytest.approx(6_000_000)  # hasta vencer, lo cobrado
