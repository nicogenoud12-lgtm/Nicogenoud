from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


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
    dividendos_2026_ars: float
    dividendos_2026_usd: float
    renta_2026_ars: float
    renta_2026_usd: float
    amortizaciones_2026_ars: float = 0.0
    amortizaciones_2026_usd: float = 0.0
    n_operaciones_2026: int
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


class CryptoSnapshotOut(BaseModel):
    id: int
    date: date
    taken_at: datetime
    total_usd: float
    total_ars: float
    cost_usd: float
    dolar_rate: float

    class Config:
        from_attributes = True
