"""crypto sales (ventas realizadas)

Revision ID: 0007_crypto_sales
Revises: 0006_holding_variacion_dia_prev
Create Date: 2026-05-29 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_crypto_sales"
down_revision: Union[str, None] = "0006_holding_variacion_dia_prev"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crypto_sales",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column("coingecko_id", sa.String(length=64), nullable=True),
        sa.Column("cantidad", sa.Numeric(28, 12), nullable=False, server_default="0"),
        sa.Column("costo_usd_unit", sa.Numeric(18, 8), nullable=True),
        sa.Column("price_usd", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column("proceeds_usd", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("cost_total_usd", sa.Numeric(18, 2), nullable=True),
        sa.Column("pnl_usd", sa.Numeric(18, 2), nullable=True),
        sa.Column("pnl_pct", sa.Numeric(18, 4), nullable=True),
        sa.Column("dolar_rate", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("notas", sa.String(length=500), nullable=True),
        sa.Column(
            "sold_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_crypto_sales_user_id", "crypto_sales", ["user_id"])
    op.create_index("ix_crypto_sales_symbol", "crypto_sales", ["symbol"])
    op.create_index("ix_crypto_sales_sold_at", "crypto_sales", ["sold_at"])


def downgrade() -> None:
    op.drop_index("ix_crypto_sales_sold_at", table_name="crypto_sales")
    op.drop_index("ix_crypto_sales_symbol", table_name="crypto_sales")
    op.drop_index("ix_crypto_sales_user_id", table_name="crypto_sales")
    op.drop_table("crypto_sales")
