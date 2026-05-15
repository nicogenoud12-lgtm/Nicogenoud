from datetime import date, datetime
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IolCredential(Base):
    __tablename__ = "iol_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    iol_username: Mapped[str] = mapped_column(String(128), nullable=False)
    iol_password_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)


class OauthToken(Base):
    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    access_token_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mercado: Mapped[str] = mapped_column(String(32), nullable=False)
    simbolo: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tipo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    clase: Mapped[str] = mapped_column(String(32), nullable=False, default="Otro")
    cantidad: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False, default=0)
    ppc: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    ultimo_precio: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    valuacion_ars: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    valuacion_usd: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    ganancia_porcentaje: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    ganancia_dinero: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    moneda: Mapped[str | None] = mapped_column(String(16), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "mercado", "simbolo", name="uq_holding_user_mercado_simbolo"),
    )


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    taken_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    total_ars: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    total_usd: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    dolar_rate: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    dolar_source: Mapped[str] = mapped_column(String(16), nullable=False, default="MEP")
    breakdown_json: Mapped[dict | list] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="scheduler")

    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_snapshot_user_date"),)


class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    iol_numero: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fecha_operada: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    fecha_liquidacion: Mapped[date | None] = mapped_column(Date, nullable=True)
    tipo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="OTRO")
    currency_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="ARS")
    estado: Mapped[str | None] = mapped_column(String(32), nullable=True)
    simbolo: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mercado: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cantidad: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    precio: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    monto_operado: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    comisiones: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    derechos_mercado: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    iva: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    monto_neto: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    moneda: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "iol_numero", name="uq_operation_user_numero"),
        Index("ix_op_user_fecha", "user_id", "fecha_operada"),
        Index("ix_op_user_event", "user_id", "event_kind"),
    )


class DolarQuote(Base):
    __tablename__ = "dolar_quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    compra: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    venta: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    promedio: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("date", "source", name="uq_dolar_date_source"),)


class CryptoHolding(Base):
    __tablename__ = "crypto_holdings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    coingecko_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cantidad: Mapped[float] = mapped_column(Numeric(28, 12), nullable=False, default=0)
    costo_usd_unit: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notas: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
