"""Asset and operation classification.

Two responsibilities:
1. classify_asset()  -> "CEDEAR" | "Acción" | "Bono" | "ON" | "FCI" | "Letra" | "Otro"
2. classify_event()  -> (event_kind, currency_kind)
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from .ons_whitelist import is_on, normalize_ticker

log = logging.getLogger(__name__)

EventKind = str  # COMPRA|VENTA|RENTA|AMORTIZACION|DIVIDENDO|SUSCRIPCION|RESCATE|CAUCION|OTRO
CurrencyKind = str  # ARS|USD_MEP|USD_CABLE


# IOL "tipo" raw strings → asset class. Kept loose because IOL labels vary.
_TIPO_MAP = {
    "cedear": "CEDEAR",
    "cedears": "CEDEAR",
    "accion": "Acción",
    "acciones": "Acción",
    "titulospublicos": "Bono",
    "titulosprivados": "ON",
    "titulospublicosextranjeros": "Bono",
    "obligacionnegociable": "ON",
    "obligacionesnegociables": "ON",
    "obligacion negociable": "ON",
    "letras": "Letra",
    "letra": "Letra",
    "fci": "FCI",
    "fondoscomunesdeinversion": "FCI",
    "fondocomun": "FCI",
    "fondo": "FCI",
    "caucion": "Caucion",
    "cauciones": "Caucion",
}


# Bonos soberanos AR (heurística por prefijo)
_SOBERANO_PREFIXES = (
    "AL29", "AL30", "AL35", "AL41", "AE38",
    "GD29", "GD30", "GD35", "GD38", "GD41", "GD46",
    "TX26", "TX28", "T2X", "TZX", "TG", "TY", "TV",
    # Bopreales (BCRA) — series B/C/D/E
    "BPOB", "BPOC", "BPOD", "BPOE",
)


def _norm(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", "", s).lower()


def classify_asset(
    *,
    simbolo: Optional[str],
    tipo: Optional[str] = None,
    descripcion: Optional[str] = None,
    mercado: Optional[str] = None,
) -> str:
    """Return one of: CEDEAR, Acción, Bono, ON, FCI, Letra, Otro."""
    sym = (simbolo or "").upper().strip()
    base, _suffix = normalize_ticker(sym)

    # 1. IOL tipo string
    norm_tipo = _norm(tipo)
    for needle, clase in _TIPO_MAP.items():
        if needle in norm_tipo:
            return clase

    # 2. ON whitelist
    if is_on(sym):
        return "ON"

    # 3. Soberanos por prefijo
    if any(base.startswith(p) for p in _SOBERANO_PREFIXES):
        return "Bono"

    # 4. Letras (Lecaps, Lecer): suelen empezar con S, T2 o L y tener formato fecha
    if re.match(r"^(S|T|LEC)[A-Z0-9]{2,5}$", sym) and "ON" not in (descripcion or "").upper():
        # Mantengo conservador
        if sym.startswith(("S", "L")):
            return "Letra"

    # 5. Mercado USA + ticker corto ASCII → asumimos Acción extranjera tratada como CEDEAR
    if mercado and "estados" in _norm(mercado):
        return "CEDEAR"

    # 6. Descripción
    desc_low = (descripcion or "").lower()
    if "cauci" in desc_low:
        return "Caucion"
    if "cedear" in desc_low:
        return "CEDEAR"
    if "obligaci" in desc_low or "negoc" in desc_low:
        return "ON"
    if "letra" in desc_low or "lecap" in desc_low or "lecer" in desc_low:
        return "Letra"
    if "bono" in desc_low or "boncer" in desc_low or "global" in desc_low:
        return "Bono"
    if "fci" in desc_low or "fondo" in desc_low:
        return "FCI"

    # 7. Fallback
    log.warning("classify_asset: unknown simbolo=%s tipo=%s desc=%s", sym, tipo, descripcion)
    return "Otro"


def _currency_kind_from(
    *, simbolo: Optional[str], moneda: Optional[str], asset_class: Optional[str] = None
) -> CurrencyKind:
    sym = (simbolo or "").upper().strip()
    _, suffix = normalize_ticker(sym)
    if suffix == "D":
        return "USD_MEP"
    if suffix == "C":
        return "USD_CABLE"
    if suffix == "O":
        # ONs argentinas with suffix O are ARS, not USD_CABLE
        if asset_class == "ON":
            return "ARS"
        return "USD_CABLE"

    m = _norm(moneda)
    if not m:
        return "ARS"
    if "peso" in m or m == "ars" or "ar$" in m:
        return "ARS"
    if "dolar" in m or "usd" in m or "us$" in m or "u$s" in m:
        # Without a suffix hint default to USD_MEP (más común en IOL para bonos AR)
        if "cable" in m or "ccl" in m:
            return "USD_CABLE"
        return "USD_MEP"
    return "ARS"


def classify_event(
    *,
    tipo: Optional[str],
    descripcion: Optional[str] = None,
    simbolo: Optional[str] = None,
    moneda: Optional[str] = None,
    asset_class: Optional[str] = None,
) -> tuple[EventKind, CurrencyKind]:
    """Normalize IOL operation type into (event_kind, currency_kind)."""
    raw = _norm(tipo)
    desc = _norm(descripcion)
    text = f"{raw} {desc}"

    # Cauciones bursátiles (colocadoras y tomadoras) — ignorar completamente.
    # Usamos "cauci" para capturar tanto "caucion" como "caución" (con tilde).
    if "cauci" in raw or "cauci" in desc:
        return "CAUCION", _currency_kind_from(simbolo=simbolo, moneda=moneda, asset_class=asset_class)

    # Priorizamos el campo estructurado `tipo` sobre la descripción para no
    # confundir eventos combinados ("Pago de renta y amortización" en el texto
    # vs un tipo claro "Pago de dividendos" o "Amortización").
    if "compra" in raw and "venta" not in raw:
        ev = "COMPRA"
    elif "venta" in raw:
        ev = "VENTA"
    elif "suscripcion" in raw:
        ev = "SUSCRIPCION"
    elif "rescate" in raw:
        ev = "RESCATE"
    elif "amortiz" in raw and "renta" not in raw:
        ev = "AMORTIZACION"
    elif "renta" in raw or "cupon" in raw:
        # Incluye "Pago de renta", "Pago de renta y amortización", "Cupón".
        ev = "RENTA"
    elif "dividend" in raw:
        # IOL a veces etiqueta renta de ON como "Pago de dividendos".
        ev = "RENTA" if asset_class == "ON" else "DIVIDENDO"
    elif "amortiz" in raw:
        ev = "AMORTIZACION"
    else:
        # `tipo` no concluyente → revisar descripción
        if "suscripcion" in desc or "suscripción" in (descripcion or "").lower():
            ev = "SUSCRIPCION"
        elif "rescate" in desc:
            ev = "RESCATE"
        elif ("renta" in desc and "amortiz" in desc):
            ev = "RENTA"
        elif "renta" in desc or "cupon" in desc or "cupón" in (descripcion or "").lower():
            ev = "RENTA"
        elif "amortiz" in desc:
            ev = "AMORTIZACION"
        elif "dividend" in desc:
            ev = "RENTA" if asset_class == "ON" else "DIVIDENDO"
        else:
            log.warning(
                "classify_event: unknown tipo=%s desc=%s simbolo=%s",
                tipo,
                descripcion,
                simbolo,
            )
            ev = "OTRO"

    cur = _currency_kind_from(simbolo=simbolo, moneda=moneda, asset_class=asset_class)
    return ev, cur
