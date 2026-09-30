"""Tests for ai_insights: armado del contexto y persistencia del resumen."""
import asyncio
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import AiInsight, Base, DolarQuote, Holding, Operation, User
from app.services import ai_insights

TODAY = date(2026, 9, 30)


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


def _seed(db, user):
    db.add(DolarQuote(date=TODAY - timedelta(days=1), source="MEP", promedio=1390))
    db.add(DolarQuote(date=TODAY, source="MEP", promedio=1400))
    db.add_all([
        Holding(user_id=user.id, mercado="bCBA", simbolo="GGAL", clase="Acción", cantidad=10,
                valuacion_ars=102000, valuacion_usd=72.86, variacion_dia=2.0, moneda="peso_Argentino"),
        # Sin variación hoy: tiene que usar la de ayer y marcarla
        Holding(user_id=user.id, mercado="bCBA", simbolo="YM34O", clase="ON", cantidad=100,
                valuacion_ars=298000, valuacion_usd=212.86, variacion_dia=0, variacion_dia_prev=-1.5,
                moneda="peso_Argentino"),
        Holding(user_id=user.id, mercado="bCBA", simbolo="CAUCION", clase="Caucion", cantidad=1,
                valuacion_ars=50000, valuacion_usd=35.7, moneda="peso_Argentino"),
    ])
    db.add(Operation(user_id=user.id, iol_numero="1", fecha_operada=TODAY - timedelta(days=3),
                     event_kind="COMPRA", currency_kind="ARS", simbolo="GGAL", cantidad=2, monto_neto=-20000))
    db.add(Operation(user_id=user.id, iol_numero="2", fecha_operada=TODAY - timedelta(days=90),
                     event_kind="COMPRA", currency_kind="ARS", simbolo="GGAL", cantidad=1, monto_neto=-9000))
    db.commit()


def test_build_context(db, user):
    _seed(db, user)
    ctx = ai_insights.build_context(db, user.id, today=TODAY)

    assert ctx["dolar_mep"][0] == {"fecha": "2026-09-30", "promedio": 1400.0}
    simbolos = [t["simbolo"] for t in ctx["tenencias"]]
    assert simbolos == ["YM34O", "GGAL"]  # ordenado por valuación, sin caución

    ggal = next(t for t in ctx["tenencias"] if t["simbolo"] == "GGAL")
    assert ggal["peso_pct"] == 25.5
    assert ggal["variacion_dia_pct"] == 2.0 and ggal["variacion_es_de_ayer"] is False

    ym = next(t for t in ctx["tenencias"] if t["simbolo"] == "YM34O")
    assert ym["variacion_dia_pct"] == -1.5 and ym["variacion_es_de_ayer"] is True

    # Sólo cuenta la variación de hoy: 102000 − 102000/1.02 = 2000
    assert ctx["cartera_iol"]["variacion_dia_estimada_ars"] == 2000.0
    # Operaciones de los últimos 30 días únicamente, monto en valor absoluto
    assert ctx["operaciones_30d"] == [{
        "fecha": "2026-09-27", "tipo": "COMPRA", "simbolo": "GGAL",
        "cantidad": 2.0, "monto_neto": 20000.0, "moneda": "ARS",
    }]


class _FakeMessages:
    def __init__(self, calls):
        self.calls = calls

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        out = kwargs["output_format"](
            titulo="Día positivo",
            resumen_dia="La cartera subió.",
            destacados=["GGAL +2%"],
            recomendaciones=[{"accion": "Mantener", "activo": "GGAL", "motivo": "Peso 25%"}],
            riesgos=["Concentración en una ON"],
        )
        return SimpleNamespace(
            stop_reason="end_turn", parsed_output=out, model="claude-opus-5-5",
            usage=SimpleNamespace(input_tokens=1000, output_tokens=300),
        )


class _FakeClient:
    calls: list = []

    def __init__(self, *args, **kwargs):
        self.beta = SimpleNamespace(messages=_FakeMessages(_FakeClient.calls))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def test_generate_requires_api_key(db, user, monkeypatch):
    monkeypatch.setattr(ai_insights.settings, "anthropic_api_key", "")
    with pytest.raises(ai_insights.AiNotConfiguredError):
        asyncio.run(ai_insights.generate(db, user.id))


def test_generate_upserts_one_per_day(db, user, monkeypatch):
    _seed(db, user)
    monkeypatch.setattr(ai_insights.settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(ai_insights.anthropic, "AsyncAnthropic", _FakeClient)
    _FakeClient.calls = []

    asyncio.run(ai_insights.generate(db, user.id))
    row = asyncio.run(ai_insights.generate(db, user.id, source="scheduler"))

    assert db.query(AiInsight).count() == 1
    assert row.source == "scheduler"
    assert row.content_json["recomendaciones"][0]["activo"] == "GGAL"
    assert row.input_tokens == 1000
    assert _FakeClient.calls[0]["fallbacks"] == "default"
