"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "iol_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("iol_username", sa.String(length=128), nullable=False),
        sa.Column("iol_password_enc", sa.LargeBinary(), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
    )

    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("access_token_enc", sa.LargeBinary(), nullable=False),
        sa.Column("refresh_token_enc", sa.LargeBinary(), nullable=True),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mercado", sa.String(length=32), nullable=False),
        sa.Column("simbolo", sa.String(length=32), nullable=False),
        sa.Column("descripcion", sa.String(length=255), nullable=True),
        sa.Column("tipo", sa.String(length=64), nullable=True),
        sa.Column("clase", sa.String(length=32), nullable=False, server_default="Otro"),
        sa.Column("cantidad", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("ppc", sa.Numeric(18, 6), nullable=True),
        sa.Column("ultimo_precio", sa.Numeric(18, 6), nullable=True),
        sa.Column("valuacion_ars", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("valuacion_usd", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("ganancia_porcentaje", sa.Numeric(10, 4), nullable=True),
        sa.Column("ganancia_dinero", sa.Numeric(18, 2), nullable=True),
        sa.Column("moneda", sa.String(length=16), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "mercado", "simbolo", name="uq_holding_user_mercado_simbolo"),
    )
    op.create_index("ix_holdings_user_id", "holdings", ["user_id"])
    op.create_index("ix_holdings_simbolo", "holdings", ["simbolo"])

    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("total_ars", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_usd", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("dolar_rate", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("dolar_source", sa.String(length=16), nullable=False, server_default="MEP"),
        sa.Column("breakdown_json", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="scheduler"),
        sa.UniqueConstraint("user_id", "date", name="uq_snapshot_user_date"),
    )
    op.create_index("ix_snap_user_id", "portfolio_snapshots", ["user_id"])
    op.create_index("ix_snap_date", "portfolio_snapshots", ["date"])

    op.create_table(
        "operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("iol_numero", sa.String(length=64), nullable=False),
        sa.Column("fecha_operada", sa.Date(), nullable=True),
        sa.Column("fecha_liquidacion", sa.Date(), nullable=True),
        sa.Column("tipo", sa.String(length=64), nullable=True),
        sa.Column("event_kind", sa.String(length=32), nullable=False, server_default="OTRO"),
        sa.Column("currency_kind", sa.String(length=16), nullable=False, server_default="ARS"),
        sa.Column("estado", sa.String(length=32), nullable=True),
        sa.Column("simbolo", sa.String(length=32), nullable=True),
        sa.Column("descripcion", sa.String(length=255), nullable=True),
        sa.Column("mercado", sa.String(length=32), nullable=True),
        sa.Column("cantidad", sa.Numeric(18, 6), nullable=True),
        sa.Column("precio", sa.Numeric(18, 6), nullable=True),
        sa.Column("monto_operado", sa.Numeric(18, 2), nullable=True),
        sa.Column("comisiones", sa.Numeric(18, 2), nullable=True),
        sa.Column("derechos_mercado", sa.Numeric(18, 2), nullable=True),
        sa.Column("iva", sa.Numeric(18, 2), nullable=True),
        sa.Column("monto_neto", sa.Numeric(18, 2), nullable=True),
        sa.Column("moneda", sa.String(length=16), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "iol_numero", name="uq_operation_user_numero"),
    )
    op.create_index("ix_op_user_id", "operations", ["user_id"])
    op.create_index("ix_op_iol_numero", "operations", ["iol_numero"])
    op.create_index("ix_op_simbolo", "operations", ["simbolo"])
    op.create_index("ix_op_fecha_operada", "operations", ["fecha_operada"])
    op.create_index("ix_op_user_fecha", "operations", ["user_id", "fecha_operada"])
    op.create_index("ix_op_user_event", "operations", ["user_id", "event_kind"])

    op.create_table(
        "dolar_quotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("compra", sa.Numeric(18, 4), nullable=True),
        sa.Column("venta", sa.Numeric(18, 4), nullable=True),
        sa.Column("promedio", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("date", "source", name="uq_dolar_date_source"),
    )
    op.create_index("ix_dolar_date", "dolar_quotes", ["date"])

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_index("ix_dolar_date", table_name="dolar_quotes")
    op.drop_table("dolar_quotes")
    for ix in ("ix_op_user_event", "ix_op_user_fecha", "ix_op_fecha_operada",
               "ix_op_simbolo", "ix_op_iol_numero", "ix_op_user_id"):
        op.drop_index(ix, table_name="operations")
    op.drop_table("operations")
    op.drop_index("ix_snap_date", table_name="portfolio_snapshots")
    op.drop_index("ix_snap_user_id", table_name="portfolio_snapshots")
    op.drop_table("portfolio_snapshots")
    op.drop_index("ix_holdings_simbolo", table_name="holdings")
    op.drop_index("ix_holdings_user_id", table_name="holdings")
    op.drop_table("holdings")
    op.drop_table("oauth_tokens")
    op.drop_table("iol_credentials")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
