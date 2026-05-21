"""add variacion_dia_prev to holdings"""
from alembic import op
import sqlalchemy as sa

revision = "0006_holding_variacion_dia_prev"
down_revision = "0005_holding_variacion_dia"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("holdings", sa.Column("variacion_dia_prev", sa.Numeric(10, 4), nullable=True))


def downgrade():
    op.drop_column("holdings", "variacion_dia_prev")
