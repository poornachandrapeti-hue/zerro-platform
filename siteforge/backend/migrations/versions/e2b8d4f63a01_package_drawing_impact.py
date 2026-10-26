"""Work package drawing impact review.

Revision ID: e2b8d4f63a01
Revises: e1a7c3d52f90
"""
from alembic import op
import sqlalchemy as sa

revision = "e2b8d4f63a01"
down_revision = "e1a7c3d52f90"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("work_packages", sa.Column("impact_state", sa.String(30), nullable=False, server_default=""))
    op.add_column("work_packages", sa.Column("impact_detail", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "work_packages",
        sa.Column("impact_revision_id", sa.Integer(), sa.ForeignKey("drawing_revisions.id"), nullable=True),
    )


def downgrade():
    op.drop_column("work_packages", "impact_revision_id")
    op.drop_column("work_packages", "impact_detail")
    op.drop_column("work_packages", "impact_state")
