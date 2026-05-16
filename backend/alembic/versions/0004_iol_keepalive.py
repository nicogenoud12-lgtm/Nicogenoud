"""iol keepalive: add last_keepalive_at to oauth_tokens

Revision ID: 0004_iol_keepalive
Revises: 0003_crypto_snapshots
Create Date: 2026-05-16 00:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_iol_keepalive"
down_revision: Union[str, None] = "0003_crypto_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "oauth_tokens",
        sa.Column("last_keepalive_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("oauth_tokens", "last_keepalive_at")
