"""Resumen diario con IA: arma el contexto de la cartera y le pide a Claude
un resumen del día más recomendaciones sobre lo que ya hay en la cartera.

El contexto sale sólo de la DB (tenencias, snapshots, operaciones, dólar,
crypto): el modelo no tiene acceso a noticias ni precios externos, así que
el prompt le pide no inventar datos de mercado.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Literal

import anthropic
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AiInsight, CryptoSnapshot, DolarQuote, Holding, Operation, PortfolioSnapshot
from . import portfolio_service

log = logging.getLogger(__name__)


class AiNotConfiguredError(RuntimeError):
    pass


class AiGenerationError(RuntimeError):
    pass


# --- Formato de salida (structured outputs) ---------------------------------


class Recomendacion(BaseModel):
    accion: Literal["Aumentar", "Mantener", "Reducir", "Vigilar", "Diversificar"]
    activo: str = Field(description="Ticker o clase de activo al que aplica")
    motivo: str = Field(description="Por qué, citando los números de la cartera")


class DailyInsight(BaseModel):
    titulo: str = Field(description="Una línea que resuma el día")
    resumen_dia: str = Field(description="Dos o tres párrafos cortos sobre cómo fue el día")
    destacados: list[str] = Field(description="Hechos puntuales del día (movimientos, pagos, dólar)")
    recomendaciones: list[Recomendacion]
    riesgos: list[str] = Field(description="Riesgos o concentraciones a tener en cuenta")


SYSTEM_PROMPT = """Sos un analista de inversiones que escribe el resumen diario de la cartera personal de un inversor argentino que opera en InvertirOnline (IOL). Escribís en español rioplatense, claro y directo, sin jerga innecesaria.

Sobre el inversor:
- Horizonte largo. En general no vende: arma la cartera con aportes periódicos y cobra renta, amortizaciones y dividendos.
- Por eso las recomendaciones apuntan sobre todo a dónde conviene destinar los próximos aportes o la reinversión de los pagos, a qué vigilar y a cuándo tendría sentido reducir una posición. No sugieras operar seguido.

Cómo trabajar:
- Usá sólo los datos del contexto JSON. No tenés acceso a noticias ni a precios fuera de lo que viene ahí: no inventes cotizaciones, índices, noticias ni eventos. Si algo no se puede saber con estos datos, no lo afirmes.
- `variacion_dia_pct` es la variación del día de cada tenencia en su moneda; si viene `variacion_es_de_ayer: true`, es la de la rueda anterior (hoy todavía no operó o es feriado/fin de semana) y tenés que decirlo así.
- Los montos en ARS y USD ya están convertidos con el MEP. Citá números concretos (porcentajes, montos, pesos en la cartera) cuando sostengan una idea.
- Las recomendaciones tienen que salir de la cartera: concentración por activo o por clase, exposición a peso vs dólar, pagos próximos que conviene reinvertir, tenencias con ganancia o pérdida grande, diversificación. Entre 3 y 5, ordenadas por importancia.
- Los riesgos: 2 a 4, concretos.
- No agregues avisos legales: la interfaz ya aclara que no es asesoramiento financiero."""


# --- Contexto ----------------------------------------------------------------


def _f(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _r(v: float, nd: int = 2) -> float:
    return round(v, nd)


def _dolar_series(db: Session, source: str = "MEP", n: int = 2) -> list[dict]:
    rows = (
        db.query(DolarQuote)
        .filter(DolarQuote.source == source)
        .order_by(DolarQuote.date.desc())
        .limit(n)
        .all()
    )
    return [{"fecha": r.date.isoformat(), "promedio": _r(_f(r.promedio))} for r in rows]


def build_context(db: Session, user_id: int, *, today: date | None = None) -> dict:
    """Arma el contexto que se le pasa al modelo. Sólo lee la DB."""
    today = today or date.today()

    dolar = _dolar_series(db, "MEP", 2)
    dolar_rate = dolar[0]["promedio"] if dolar else 0.0
    kpis = portfolio_service.compute_kpis(db, user_id, dolar_rate=dolar_rate, dolar_source="MEP")

    holdings = (
        db.query(Holding)
        .filter(Holding.user_id == user_id, Holding.clase != "Caucion")
        .order_by(Holding.valuacion_ars.desc())
        .all()
    )
    total_ars = kpis["total_ars"] or 0.0

    tenencias = []
    variacion_dia_ars = 0.0
    for h in holdings:
        val_ars = _f(h.valuacion_ars)
        var = h.variacion_dia
        de_ayer = False
        if var is None or _f(var) == 0:
            if h.variacion_dia_prev is not None:
                var, de_ayer = h.variacion_dia_prev, True
        var_pct = _f(var) if var is not None else None
        if var_pct is not None and not de_ayer and var_pct > -100:
            # Variación en pesos del día: valor actual − valor al cierre anterior
            variacion_dia_ars += val_ars - val_ars / (1 + var_pct / 100)
        tenencias.append(
            {
                "simbolo": h.simbolo,
                "descripcion": h.descripcion,
                "clase": h.clase,
                "moneda": h.moneda,
                "cantidad": _f(h.cantidad),
                "valuacion_ars": _r(val_ars),
                "valuacion_usd": _r(_f(h.valuacion_usd)),
                "peso_pct": _r(val_ars / total_ars * 100) if total_ars else None,
                "ganancia_pct": _r(_f(h.ganancia_porcentaje)) if h.ganancia_porcentaje is not None else None,
                "variacion_dia_pct": _r(var_pct) if var_pct is not None else None,
                "variacion_es_de_ayer": de_ayer,
            }
        )

    snaps = (
        db.query(PortfolioSnapshot)
        .filter(
            PortfolioSnapshot.user_id == user_id,
            PortfolioSnapshot.date >= today - timedelta(days=30),
        )
        .order_by(PortfolioSnapshot.date.asc())
        .all()
    )
    evolucion = [
        {"fecha": s.date.isoformat(), "total_ars": _r(_f(s.total_ars)), "total_usd": _r(_f(s.total_usd))}
        for s in snaps
        if _f(s.total_ars) > 0
    ]

    ops = (
        db.query(Operation)
        .filter(
            Operation.user_id == user_id,
            Operation.fecha_operada >= today - timedelta(days=30),
        )
        .order_by(Operation.fecha_operada.desc())
        .limit(40)
        .all()
    )
    operaciones = [
        {
            "fecha": o.fecha_operada.isoformat() if o.fecha_operada else None,
            "tipo": o.event_kind,
            "simbolo": o.simbolo,
            "cantidad": _f(o.cantidad) if o.cantidad is not None else None,
            "monto_neto": _r(abs(_f(o.monto_neto if o.monto_neto is not None else o.monto_operado))),
            "moneda": "USD" if o.currency_kind in ("USD_MEP", "USD_CABLE") else "ARS",
        }
        for o in ops
    ]

    horizonte = (today + timedelta(days=60)).isoformat()
    proximos_pagos = [
        {
            "simbolo": e["simbolo"],
            "tipo": e["event_kind"],
            "fecha_estimada": e["estimated_date"],
            "monto_estimado": e["last_amount"],
            "moneda": "USD" if str(e.get("currency_kind", "")).startswith("USD") else "ARS",
        }
        for e in portfolio_service.upcoming_events(db, user_id)
        if e["estimated_date"] <= horizonte
    ]

    crypto = None
    cs = (
        db.query(CryptoSnapshot)
        .filter(CryptoSnapshot.user_id == user_id)
        .order_by(CryptoSnapshot.date.desc())
        .first()
    )
    if cs is not None and _f(cs.total_usd) > 0:
        items = cs.breakdown_json if isinstance(cs.breakdown_json, list) else []
        crypto = {
            "fecha": cs.date.isoformat(),
            "total_usd": _r(_f(cs.total_usd)),
            "costo_usd": _r(_f(cs.cost_usd)),
            "activos": [
                {
                    "simbolo": it.get("symbol"),
                    "valor_usd": _r(_f(it.get("value_usd"))),
                    "ganancia_pct": _r(_f(it.get("pnl_pct"))) if it.get("pnl_pct") is not None else None,
                }
                for it in items
                if isinstance(it, dict)
            ],
        }

    return {
        "fecha": today.isoformat(),
        "dia_semana": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][today.weekday()],
        "dolar_mep": dolar,
        "cartera_iol": {
            "total_ars": kpis["total_ars"],
            "total_usd": kpis["total_usd"],
            "variacion_dia_estimada_ars": _r(variacion_dia_ars),
            "pnl_no_realizada_ars": kpis["pnl_no_realizada_ars"],
            "pnl_no_realizada_usd": kpis["pnl_no_realizada_usd"],
            "distribucion_por_clase": kpis["distribucion_por_clase"],
            f"cobrado_{kpis['kpi_year']}": {
                "renta_usd": kpis["renta_usd"],
                "dividendos_usd": kpis["dividendos_usd"],
                "amortizaciones_usd": kpis["amortizaciones_usd"],
            },
        },
        "tenencias": tenencias,
        "evolucion_30d": evolucion,
        "operaciones_30d": operaciones,
        "proximos_pagos_60d": proximos_pagos,
        "crypto": crypto,
    }


# --- Generación --------------------------------------------------------------


def is_enabled() -> bool:
    return bool(settings.anthropic_api_key)


async def generate(db: Session, user_id: int, *, source: str = "manual") -> AiInsight:
    if not is_enabled():
        raise AiNotConfiguredError("Falta ANTHROPIC_API_KEY en backend/.env")

    today = date.today()
    context = build_context(db, user_id, today=today)
    if not context["tenencias"]:
        raise AiGenerationError("No hay tenencias cargadas para analizar")

    user_msg = (
        "Contexto de la cartera al día de hoy (JSON):\n\n"
        + json.dumps(context, ensure_ascii=False, default=str)
        + "\n\nEscribí el resumen del día y las recomendaciones."
    )

    try:
        async with anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=180.0) as client:
            resp = await client.beta.messages.parse(
                model=settings.ai_model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                output_config={"effort": "medium"},
                output_format=DailyInsight,
                # Si el modelo rechaza el pedido, la API lo reintenta con otro modelo
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
    except anthropic.AuthenticationError as e:
        raise AiGenerationError("API key de Anthropic inválida") from e
    except anthropic.RateLimitError as e:
        raise AiGenerationError("Límite de uso de la API de Anthropic, probá en unos minutos") from e
    except anthropic.APIStatusError as e:
        raise AiGenerationError(f"Error de la API de Anthropic ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise AiGenerationError("No se pudo conectar con la API de Anthropic") from e

    if resp.stop_reason == "refusal":
        raise AiGenerationError("El modelo no generó el resumen (rechazo)")
    if resp.stop_reason == "max_tokens" or resp.parsed_output is None:
        raise AiGenerationError("La respuesta del modelo vino incompleta")

    content = resp.parsed_output.model_dump()
    row = (
        db.query(AiInsight)
        .filter(AiInsight.user_id == user_id, AiInsight.date == today)
        .first()
    )
    if row is None:
        row = AiInsight(user_id=user_id, date=today)
        db.add(row)
    row.created_at = datetime.now(tz=timezone.utc)
    row.model = resp.model
    row.source = source
    row.content_json = content
    row.input_tokens = resp.usage.input_tokens
    row.output_tokens = resp.usage.output_tokens
    db.commit()
    db.refresh(row)
    log.info(
        "ai insight generado user=%s model=%s in=%s out=%s",
        user_id, resp.model, resp.usage.input_tokens, resp.usage.output_tokens,
    )
    return row
