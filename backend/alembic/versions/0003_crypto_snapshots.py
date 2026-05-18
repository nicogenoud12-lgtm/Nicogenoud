"""crypto snapshots

Revision ID: 0003_crypto_snapshots
Revises: 0002_crypto_holdings
Create Date: 2026-05-15 00:00:01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_crypto_snapshots"
down_revision: Union[str, None] = "0002_crypto_holdings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crypto_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "taken_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("total_usd", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_ars", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("dolar_rate", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("breakdown_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("user_id", "date", name="uq_crypto_snapshot_user_date"),
    )
    op.create_index("ix_crypto_snap_user_id", "crypto_snapshots", ["user_id"])
    op.create_index("ix_crypto_snap_date", "crypto_snapshots", ["date"])


def downgrade() -> None:
    op.drop_index("ix_crypto_snap_date", table_name="crypto_snapshots")
    op.drop_index("ix_crypto_snap_user_id", table_name="crypto_snapshots")
    op.drop_table("crypto_snapshots")
