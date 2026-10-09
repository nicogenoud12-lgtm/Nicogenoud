"""Operations sync from IOL — idempotent upsert by (user_id, iol_numero)."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Callable

import httpx
from sqlalchemy.orm import Session

from ..models import Operation
from .classifier import classify_asset, classify_event
from .dolar_service import backfill_historical_mep
from .iol_client import IolApiError, IolClient, RateLimitError

# Errores de IOL que no son de login: un 500 o un rango que no banca
IOL_FETCH_ERRORS = (IolApiError, httpx.HTTPError, RateLimitError)

# Comisión + derechos + IVA en IOL rondan el 1%: un `monto` más de 3% arriba de
# montoOperado no es "con comisiones", es otra unidad.
MAX_FEE_FACTOR = 1.03

_ENRICHABLE_KINDS = ("DIVIDENDO", "RENTA", "AMORTIZACION", "COMPRA", "VENTA", "SUSCRIPCION", "RESCATE")

log = logging.getLogger(__name__)


def _parse_date(v: Any) -> date | None:
    if not v:
        return None
    if isinstance(v, date):
        return v
    s = str(v)
    # IOL puede devolver "2026-01-15T00:00:00" o "2026-01-15"
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _str(v) -> str | None:
    return None if v is None else str(v)


async def sync_operations(
    db: Session,
    user_id: int,
    *,
    year: int,
    hasta: date | None = None,
) -> int:
    """Pull /operaciones for the given year, upsert by iol_numero. Returns # rows touched."""
    desde = date(year, 1, 1)
    # Un año pasado termina el 31/12: si no, sincronizar 2019 traía (y cruzaba con
    # movimientos) todo desde 2019 hasta hoy.
    hasta = hasta or min(date.today(), date(year, 12, 31))
    async with IolClient(db, user_id) as client:
        ops = await _fetch_operaciones(client, desde, hasta)

    log.info("sync_operations: IOL returned %d raw rows (user=%d, year=%d)", len(ops), user_id, year)
    if not ops and year < date.today().year:
        # Año pasado sin actividad (pasa al recorrer el historial hacia atrás):
        # no hay nada que enriquecer ni convertir.
        return 0

    touched = 0
    skipped_no_numero = 0
    for raw in ops:
        if not isinstance(raw, dict):
            continue
        numero = (
            raw.get("numero")
            or raw.get("Numero")
            or raw.get("numeroOperacion")
            or raw.get("numeroOrden")
            or raw.get("id")
        )
        if numero is None:
            skipped_no_numero += 1
            if skipped_no_numero <= 3:
                log.warning("sync_operations: row without numero: keys=%s", list(raw.keys()))
            continue
        iol_numero = str(numero)

        simbolo = raw.get("simbolo") or raw.get("Simbolo")
        descripcion = raw.get("descripcion") or raw.get("Descripcion")
        tipo = raw.get("tipo") or raw.get("Tipo")
        moneda = raw.get("moneda") or raw.get("Moneda")
        mercado = raw.get("mercado") or raw.get("Mercado")
        estado = raw.get("estado") or raw.get("Estado")

        asset_class = classify_asset(
            simbolo=simbolo, tipo=None, descripcion=descripcion, mercado=mercado
        )
        event_kind, currency_kind = classify_event(
            tipo=tipo,
            descripcion=descripcion,
            simbolo=simbolo,
            moneda=moneda,
            asset_class=asset_class,
        )

        op = (
            db.query(Operation)
            .filter(Operation.user_id == user_id, Operation.iol_numero == iol_numero)
            .first()
        )
        if op is None:
            op = Operation(user_id=user_id, iol_numero=iol_numero)
            db.add(op)

        op.fecha_operada = _parse_date(raw.get("fechaOperada") or raw.get("fechaOrden") or raw.get("fecha"))
        op.fecha_liquidacion = _parse_date(raw.get("fechaLiquidacion"))
        op.tipo = _str(tipo)
        op.event_kind = event_kind
        op.currency_kind = currency_kind
        op.estado = _str(estado)
        op.simbolo = _str(simbolo)
        op.descripcion = _str(descripcion)[:255] if descripcion else None
        op.mercado = _str(mercado)
        op.cantidad = _f(raw.get("cantidadOperada") or raw.get("cantidad"))
        op.precio = _f(raw.get("precioOperado") or raw.get("precio"))
        monto_operado = _f(raw.get("montoOperado"))
        monto_raw = _f(raw.get("monto"))
        op.monto_operado = monto_operado or monto_raw
        op.comisiones = 0.0
        op.derechos_mercado = 0.0
        op.iva = 0.0

        gross = op.monto_operado or 0.0
        if event_kind in ("COMPRA", "SUSCRIPCION"):
            # IOL no envía comisión en /operaciones. Para COMPRAs el campo `monto`
            # incluye las fees (total debitado), mientras que montoOperado es el valor bruto.
            # Sólo usamos monto si la diferencia es del orden de las comisiones: en bonos
            # `monto` puede venir calculado sobre valor nominal (≈100× el real) y eso
            # inflaba las compras y los flujos del gráfico.
            fees_plausible = (
                monto_raw and monto_operado and monto_operado < monto_raw <= monto_operado * MAX_FEE_FACTOR
            )
            total_pagado = monto_raw if fees_plausible else gross
            op.monto_neto = -total_pagado
        elif event_kind in ("VENTA", "RESCATE"):
            # Para VENTAs no hay forma de obtener la comisión sin movimientos.
            # Se usa montoOperado (bruto); el enriquecimiento con movimientos lo corrige si funciona.
            op.monto_neto = gross
        else:
            op.monto_neto = gross
        op.moneda = _str(moneda)
        op.raw_json = raw
        touched += 1

    db.commit()
    log.info(
        "sync_operations: upserted=%d skipped_no_numero=%d user=%d year=%d",
        touched, skipped_no_numero, user_id, year,
    )

    # Enrich dividends/renta with net amounts from /movimientos
    enriched = await _enrich_with_movimientos(db, user_id, desde, hasta)
    log.info("sync_operations: enriched %d dividend/renta rows from movimientos", enriched)

    # Backfill historical MEP rates so pnl.py can convert amounts to a single currency
    inserted_mep = await backfill_historical_mep(db, desde=desde, hasta=date.today())
    if inserted_mep:
        log.info("sync_operations: backfilled %d MEP historical rows", inserted_mep)

    return touched


# Recorrido del historial hacia atrás: se corta tras varios años seguidos sin
# operaciones (una vez encontrada alguna) o al llegar al piso.
HISTORY_FLOOR_YEAR = 2000
HISTORY_EMPTY_STREAK = 5


def _split_range(desde: date, hasta: date, months: int) -> list[tuple[date, date]]:
    out = []
    start = desde
    while start <= hasta:
        m = start.month - 1 + months
        nxt = date(start.year + m // 12, m % 12 + 1, 1)
        out.append((start, min(nxt - timedelta(days=1), hasta)))
        start = nxt
    return out


async def _fetch_operaciones(client: IolClient, desde: date, hasta: date) -> list:
    """Pide las operaciones del rango; si IOL da error, por trimestres y después por meses.

    IOL a veces responde 500 a un año entero (o a años viejos). Si ningún tramo
    responde, se propaga el error para que el llamador decida.
    """
    try:
        return await client.get_operaciones(estado="terminadas", desde=desde, hasta=hasta)
    except IOL_FETCH_ERRORS as e:
        log.warning("operaciones %s→%s fallaron (%s): se piden por trimestre", desde, hasta, e)

    ops: list = []
    failed: list[tuple[date, date]] = []
    last_error: Exception | None = None
    for q_desde, q_hasta in _split_range(desde, hasta, 3):
        try:
            ops.extend(await client.get_operaciones(estado="terminadas", desde=q_desde, hasta=q_hasta))
        except IOL_FETCH_ERRORS as e:
            failed.append((q_desde, q_hasta))
            last_error = e
    if failed and len(failed) == len(_split_range(desde, hasta, 3)):
        raise last_error  # nada respondió: el período no está disponible
    for q_desde, q_hasta in failed:
        for m_desde, m_hasta in _split_range(q_desde, q_hasta, 1):
            try:
                ops.extend(await client.get_operaciones(estado="terminadas", desde=m_desde, hasta=m_hasta))
            except IOL_FETCH_ERRORS as e:
                log.warning("operaciones %s→%s no disponibles: %s", m_desde, m_hasta, e)
    return ops


async def sync_year_safe(db: Session, user_id: int, year: int) -> int | None:
    """Como sync_operations, pero un error de IOL en ese año devuelve None en vez de cortar."""
    try:
        return await sync_operations(db, user_id, year=year)
    except IOL_FETCH_ERRORS as e:
        db.rollback()
        log.warning("sync de %d falló, se saltea: %s", year, e)
        return None


async def sync_history(db: Session, user_id: int, progress: Callable[[str], None]) -> dict:
    """Sincroniza año por año hacia atrás hasta agotar el historial de IOL."""
    found = 0
    oldest = None
    empty_streak = 0
    failed: list[int] = []
    for year in range(date.today().year, HISTORY_FLOOR_YEAR - 1, -1):
        progress(f"Año {year}" + (f" · {found} operaciones encontradas" if found else ""))
        n = await sync_year_safe(db, user_id, year)
        if n is None:
            # Un año que IOL no devuelve cuenta como vacío para cortar el recorrido
            failed.append(year)
            n = 0
        if n > 0:
            found += n
            oldest = year
            empty_streak = 0
        elif found > 0:
            empty_streak += 1
            if empty_streak >= HISTORY_EMPTY_STREAK:
                break
    # Sólo importan los fallidos dentro del historial (los de antes de empezar son esperables)
    failed = [y for y in failed if oldest is not None and y > oldest]
    return {"found": found, "oldest": oldest, "fallidos": sorted(failed)}


async def _enrich_with_movimientos(
    db: Session,
    user_id: int,
    desde: date,
    hasta: date,
) -> int:
    """Overwrite monto_neto for renta/dividendos with the net from IOL /movimientos."""
    async with IolClient(db, user_id) as client:
        try:
            moves = await client.get_movimientos(desde=desde, hasta=hasta)
        except Exception as e:
            log.warning("movimientos fetch failed — skipping net enrichment: %s", e)
            return 0

    if not moves:
        return 0

    by_numero = {str(m.get("numero") or m.get("id") or ""): m for m in moves if isinstance(m, dict)}
    log.info("movimientos: total=%d", len(moves))

    ops = (
        db.query(Operation)
        .filter(
            Operation.user_id == user_id,
            Operation.event_kind.in_(_ENRICHABLE_KINDS),
            Operation.fecha_operada >= desde,
            Operation.fecha_operada <= hasta,
        )
        .all()
    )

    updated = 0
    for op in ops:
        m = by_numero.get(op.iol_numero)
        if not m:
            continue
        neto = _f(m.get("monto") or m.get("importe") or m.get("montoNeto"))
        if neto is not None and neto != 0:
            # COMPRA/SUSCRIPCION = money out → negative; VENTA/RESCATE y créditos = positive
            if op.event_kind in ("COMPRA", "SUSCRIPCION"):
                op.monto_neto = -abs(neto)
            else:
                op.monto_neto = abs(neto)
            updated += 1

    if updated:
        db.commit()
    return updated
