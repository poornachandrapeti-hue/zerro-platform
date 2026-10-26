"""Manpower daily returns and the manpower.returns permission. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "b7d3e9a15c28"
down_revision = "f6a2d8e41c93"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mp_daily_returns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("hr_shifts.id"), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="Submitted"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("return_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("accepted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "work_date", "shift_id", name="uq_mp_return_day"),
        sa.CheckConstraint("state IN ('Submitted', 'Returned', 'Accepted')", name="ck_mp_return_state"),
    )
    for column in ("organization_id", "project_id", "work_date"):
        op.create_index(f"ix_mp_daily_returns_{column}", "mp_daily_returns", [column])

    op.create_table(
        "mp_return_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("return_id", sa.Integer(), sa.ForeignKey("mp_daily_returns.id"), nullable=False),
        sa.Column("personnel_id", sa.Integer(), sa.ForeignKey("hr_personnel.id"), nullable=False),
        sa.Column("planned_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attended_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("booked_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attendance", sa.String(30), nullable=False, server_default=""),
        sa.Column("flags", sa.Text(), nullable=False, server_default=""),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_mp_return_lines_return_id", "mp_return_lines", ["return_id"])

    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
