"""Manpower activity assignments and the manpower.allocate permission. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "f6a2d8e41c93"
down_revision = "e3f9a6c17b42"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mp_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("hr_shifts.id"), nullable=False),
        sa.Column("personnel_id", sa.Integer(), sa.ForeignKey("hr_personnel.id"), nullable=False),
        sa.Column("deployment_id", sa.Integer(), sa.ForeignKey("hr_deployments.id"), nullable=False),
        sa.Column("crew_id", sa.Integer(), sa.ForeignKey("hr_crews.id"), nullable=True),
        sa.Column("demand_id", sa.Integer(), sa.ForeignKey("hr_requests.id"), nullable=True),
        sa.Column("planned_minutes", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("state", sa.String(20), nullable=False, server_default="Proposed"),
        sa.Column("release_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("state IN ('Proposed', 'Confirmed', 'Released')", name="ck_mp_assignment_state"),
        sa.CheckConstraint("planned_minutes > 0", name="ck_mp_assignment_minutes"),
    )
    for column in ("organization_id", "project_id", "activity_id", "work_date", "personnel_id"):
        op.create_index(f"ix_mp_assignments_{column}", "mp_assignments", [column])

    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
