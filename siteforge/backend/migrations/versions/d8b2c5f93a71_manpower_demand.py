"""Manpower demand fields on the shared workforce request, and manpower permissions. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "d8b2c5f93a71"
down_revision = "c7a1b4e82d69"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hr_requests", sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=True))
    op.add_column("hr_requests", sa.Column("grade_id", sa.Integer(), sa.ForeignKey("hr_masters.id"), nullable=True))
    op.add_column("hr_requests", sa.Column("required_hours", sa.Integer(), nullable=True))
    op.add_column("hr_requests", sa.Column("required_mobilization", sa.Date(), nullable=True))

    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
