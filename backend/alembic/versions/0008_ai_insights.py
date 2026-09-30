"""ai insights (resumen diario con IA)

Revision ID: 0008_ai_insights
Revises: 0007_crypto_sales
Create Date: 2026-09-30 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_ai_insights"
down_revision: Union[str, None] = "0007_crypto_sales"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_insights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="manual"),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.UniqueConstraint("user_id", "date", name="uq_ai_insight_user_date"),
    )
    op.create_index("ix_ai_insights_user_id", "ai_insights", ["user_id"])
    op.create_index("ix_ai_insights_date", "ai_insights", ["date"])


def downgrade() -> None:
    op.drop_index("ix_ai_insights_date", table_name="ai_insights")
    op.drop_index("ix_ai_insights_user_id", table_name="ai_insights")
    op.drop_table("ai_insights")
