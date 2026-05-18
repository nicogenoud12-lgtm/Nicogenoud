"""crypto holdings

Revision ID: 0002_crypto_holdings
Revises: 0001_initial
Create Date: 2026-05-15 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_crypto_holdings"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crypto_holdings",
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
        sa.Column("exchange", sa.String(length=64), nullable=True),
        sa.Column("notas", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_crypto_holdings_user_id", "crypto_holdings", ["user_id"])
    op.create_index("ix_crypto_holdings_symbol", "crypto_holdings", ["symbol"])


def downgrade() -> None:
    op.drop_index("ix_crypto_holdings_symbol", table_name="crypto_holdings")
    op.drop_index("ix_crypto_holdings_user_id", table_name="crypto_holdings")
    op.drop_table("crypto_holdings")
