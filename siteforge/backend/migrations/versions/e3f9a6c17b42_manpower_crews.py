"""Manpower crew fields on the shared crew: name, trade, work location, and supervisor. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "e3f9a6c17b42"
down_revision = "d8b2c5f93a71"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hr_crews", sa.Column("name", sa.String(120), nullable=False, server_default=""))
    op.add_column("hr_crews", sa.Column("trade_id", sa.Integer(), sa.ForeignKey("hr_masters.id"), nullable=True))
    op.add_column("hr_crews", sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True))
    op.add_column("hr_crews", sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))


def downgrade():
    pass
