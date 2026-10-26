"""HR leave, temporary unavailability, and overtime. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "z4d8e1f59a36"
down_revision = "y3c7d0e48f25"
branch_labels = None
depends_on = None

STATUSES = "status IN ('Draft', 'Pending Approval', 'Approved', 'Returned', 'Rejected', 'Cancelled')"


def _audit_columns():
    return [
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    op.drop_constraint("ck_hr_master_kind", "hr_masters", type_="check")
    op.create_check_constraint(
        "ck_hr_master_kind",
        "hr_masters",
        "kind IN ('Designation', 'Trade', 'Skill grade', 'Training type', 'Document requirement', 'Leave type')",
    )

    op.create_table(
        "hr_leaves",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("personnel_id", sa.Integer(), sa.ForeignKey("hr_personnel.id"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("leave_type_id", sa.Integer(), sa.ForeignKey("hr_masters.id"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Draft"),
        sa.Column("status_reason", sa.Text(), nullable=False, server_default=""),
        *_audit_columns(),
        sa.CheckConstraint(STATUSES, name="ck_hr_leave_status"),
    )
    op.create_index("ix_hr_leaves_organization_id", "hr_leaves", ["organization_id"])
    op.create_index("ix_hr_leaves_project_id", "hr_leaves", ["project_id"])
    op.create_index("ix_hr_leaves_personnel_id", "hr_leaves", ["personnel_id"])

    op.create_table(
        "hr_overtime",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("personnel_id", sa.Integer(), sa.ForeignKey("hr_personnel.id"), nullable=True),
        sa.Column("crew_id", sa.Integer(), sa.ForeignKey("hr_crews.id"), nullable=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("hr_shifts.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
        sa.Column("requested_minutes", sa.Integer(), nullable=False),
        sa.Column("approved_minutes", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Draft"),
        sa.Column("status_reason", sa.Text(), nullable=False, server_default=""),
        *_audit_columns(),
        sa.CheckConstraint(STATUSES, name="ck_hr_overtime_status"),
        sa.CheckConstraint("requested_minutes > 0", name="ck_hr_overtime_requested"),
        sa.CheckConstraint("(personnel_id IS NULL) <> (crew_id IS NULL)", name="ck_hr_overtime_target"),
    )
    op.create_index("ix_hr_overtime_organization_id", "hr_overtime", ["organization_id"])
    op.create_index("ix_hr_overtime_project_id", "hr_overtime", ["project_id"])

    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
