"""add variacion_dia to holdings"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("holdings", sa.Column("variacion_dia", sa.Numeric(10, 4), nullable=True))


def downgrade():
    op.drop_column("holdings", "variacion_dia")
