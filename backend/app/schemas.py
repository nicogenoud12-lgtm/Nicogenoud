from datetime import date, datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    id: int
    username: str
    is_admin: bool
    iol_connected: bool


class IolConnectRequest(BaseModel):
    iol_username: str
    iol_password: str


class IolStatusResponse(BaseModel):
    connected: bool
    iol_username: Optional[str] = None
    connected_at: Optional[datetime] = None
    access_expires_at: Optional[datetime] = None
    refresh_expires_at: Optional[datetime] = None
    last_keepalive_at: Optional[datetime] = None
    last_error: Optional[str] = None


class HoldingOut(BaseModel):
    id: int
    mercado: str
    simbolo: str
    descripcion: Optional[str]
    tipo: Optional[str]
    clase: str
    cantidad: float
    ppc: Optional[float]
    ultimo_precio: Optional[float]
    valuacion_ars: float
    valuacion_usd: float
    ganancia_porcentaje: Optional[float]
    ganancia_dinero: Optional[float]
    variacion_dia: Optional[float] = None
    variacion_dia_prev: Optional[float] = None
    moneda: Optional[str]
    updated_at: datetime

    class Config:
        from_attributes = True


class KpiBreakdownItem(BaseModel):
    clase: str
    valor_ars: float
    valor_usd: float
    pct: float


class KpisResponse(BaseModel):
    total_ars: float
    total_usd: float
    dolar_rate: float
    dolar_source: str
    pnl_no_realizada_ars: float
    pnl_no_realizada_usd: float
    dividendos_ars: float
    dividendos_usd: float
    renta_ars: float
    renta_usd: float
    amortizaciones_ars: float = 0.0
    amortizaciones_usd: float = 0.0
    n_operaciones: int
    kpi_year: int
    distribucion_por_clase: list[KpiBreakdownItem]


class OperationOut(BaseModel):
    id: int
    iol_numero: str
    fecha_operada: Optional[date]
    fecha_liquidacion: Optional[date]
    tipo: Optional[str]
    event_kind: str
    currency_kind: str
    estado: Optional[str]
    simbolo: Optional[str]
    descripcion: Optional[str]
    mercado: Optional[str]
    cantidad: Optional[float]
    precio: Optional[float]
    monto_operado: Optional[float]
    comisiones: Optional[float]
    derechos_mercado: Optional[float]
    iva: Optional[float]
    monto_neto: Optional[float]
    moneda: Optional[str]
    monto_ars: Optional[float] = None
    monto_usd: Optional[float] = None

    class Config:
        from_attributes = True


class OperationsSummary(BaseModel):
    year: Optional[int] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    count: int
    total_compras_ars: float
    total_ventas_ars: float
    total_compras_usd: float
    total_ventas_usd: float
    total_dividendos_ars: float
    total_dividendos_usd: float
    total_renta_ars: float
    total_renta_usd: float
    total_amortizaciones_ars: float = 0.0
    total_amortizaciones_usd: float = 0.0
    fx_source: str = "MEP"
    fx_missing_count: int = 0
    by_simbolo: list[dict[str, Any]]
    by_mes: list[dict[str, Any]]


class DolarQuoteOut(BaseModel):
    date: date
    source: str
    compra: Optional[float]
    venta: Optional[float]
    promedio: float

    class Config:
        from_attributes = True


class SnapshotOut(BaseModel):
    id: int
    date: date
    taken_at: datetime
    total_ars: float
    total_usd: float
    dolar_rate: float
    dolar_source: str
    source: str
    breakdown_json: list = []
    # Aportes netos (+) / retiros (−) desde el snapshot anterior, para que la
    # variación diaria mida rendimiento y no plata que entró o salió.
    flujo_ars: float = 0.0
    flujo_usd: float = 0.0
    flujo_por_clase: dict[str, dict[str, float]] = {}
    # Renta + dividendos cobrados en el tramo (rendimiento, no aporte)
    ingreso_ars: float = 0.0
    ingreso_usd: float = 0.0
    ingreso_por_clase: dict[str, dict[str, float]] = {}
    # Amortizaciones cobradas en el tramo, por símbolo de la tenencia
    amort_por_simbolo: dict[str, dict[str, float]] = {}

    class Config:
        from_attributes = True


class SettingsResponse(BaseModel):
    settings: dict[str, str]


class SettingsUpdate(BaseModel):
    settings: dict[str, str] = Field(default_factory=dict)


class CryptoHoldingIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    name: Optional[str] = Field(default=None, max_length=128)
    coingecko_id: Optional[str] = Field(default=None, max_length=64)
    cantidad: float
    costo_usd_unit: Optional[float] = None
    exchange: Optional[str] = Field(default=None, max_length=64)
    notas: Optional[str] = Field(default=None, max_length=500)


class CryptoHoldingOut(CryptoHoldingIn):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CoinSearchResult(BaseModel):
    id: str
    symbol: str
    name: str
    thumb: Optional[str] = None
    market_cap_rank: Optional[int] = None


class CryptoReportItem(BaseModel):
    id: int
    symbol: str
    name: Optional[str]
    coingecko_id: Optional[str]
    cantidad: float
    costo_usd_unit: Optional[float]
    costo_total_usd: Optional[float]
    price_usd: Optional[float]
    price_ars: Optional[float]
    value_usd: Optional[float]
    value_ars: Optional[float]
    pnl_usd: Optional[float]
    pnl_pct: Optional[float]
    change_24h_pct: Optional[float]
    change_7d_pct: Optional[float] = None
    pct_portfolio: float
    exchange: Optional[str]
    has_price: bool


class CryptoReport(BaseModel):
    items: list[CryptoReportItem]
    total_value_usd: float
    total_value_ars: float
    total_cost_usd: float
    pnl_total_usd: float
    pnl_total_pct: Optional[float]
    ars_rate: float
    dolar_source: str
    fetched_at: datetime
    missing_coingecko: list[str]
    fetch_error: Optional[str] = None


def _as_utc(v: Optional[datetime]) -> Optional[datetime]:
    """SQLite devuelve los DateTime naive (en UTC, por `func.now()`). Sin zona,
    el browser los lee como hora local y una venta a las 22:30 ART aparece al
    día siguiente. Los marcamos como UTC para que salgan con "Z"."""
    if v is None:
        return v
    if v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v.astimezone(timezone.utc)


class CryptoSnapshotOut(BaseModel):
    id: int
    date: date
    taken_at: datetime
    total_usd: float
    total_ars: float
    cost_usd: float
    dolar_rate: float
    # Plata que entró (+) / salió (-) del portfolio crypto desde el snapshot
    # anterior de la lista. 0 en el primero; ARS null si no hay cotización.
    flujo_usd: float = 0.0
    flujo_ars: Optional[float] = None

    _taken_at_utc = field_validator("taken_at")(_as_utc)

    class Config:
        from_attributes = True


class CryptoSellIn(BaseModel):
    """Venta de una tenencia. `price_usd` opcional — si no se manda, se toma el
    precio en vivo (Binance/CoinGecko)."""

    cantidad: float = Field(gt=0)
    price_usd: Optional[float] = Field(default=None, gt=0)
    notas: Optional[str] = Field(default=None, max_length=500)


class CryptoSaleOut(BaseModel):
    id: int
    symbol: str
    name: Optional[str]
    coingecko_id: Optional[str]
    cantidad: float
    costo_usd_unit: Optional[float]
    price_usd: float
    proceeds_usd: float
    cost_total_usd: Optional[float]
    pnl_usd: Optional[float]
    pnl_pct: Optional[float]
    dolar_rate: float
    notas: Optional[str]
    sold_at: datetime

    _sold_at_utc = field_validator("sold_at")(_as_utc)

    class Config:
        from_attributes = True


class CryptoSalesReport(BaseModel):
    items: list[CryptoSaleOut]
    total_proceeds_usd: float
    total_cost_usd: float
    total_pnl_usd: float
    total_pnl_pct: Optional[float]
    # Suma del P&L de cada venta convertido con la cotización de esa venta.
    total_pnl_ars: float = 0.0
    ars_rate: float
    dolar_source: str
