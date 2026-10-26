"""HR shifts, crews, attendance, corrections, and period locks. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "y3c7d0e48f25"
down_revision = "x2b6c9d37e14"
branch_labels = None
depends_on = None


def _audit_columns():
    return [
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    op.create_table(
        "hr_shifts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("code_key", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("break_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attribution", sa.String(20), nullable=False, server_default="Start day"),
        sa.Column("calendar", sa.String(120), nullable=False, server_default=""),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
        sa.UniqueConstraint("project_id", "code_key", name="uq_hr_shift_code"),
        sa.CheckConstraint("attribution IN ('Start day', 'End day')", name="ck_hr_shift_attribution"),
        sa.CheckConstraint("break_minutes >= 0", name="ck_hr_shift_break"),
    )
    op.create_index("ix_hr_shifts_organization_id", "hr_shifts", ["organization_id"])
    op.create_index("ix_hr_shifts_project_id", "hr_shifts", ["project_id"])

    op.create_table(
        "hr_crews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("code_key", sa.String(40), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("hr_personnel.id"), nullable=True),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("hr_shifts.id"), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit_columns(),
        sa.UniqueConstraint("project_id", "code_key", name="uq_hr_crew_code"),
    )
    op.create_index("ix_hr_crews_organization_id", "hr_crews", ["organization_id"])
    op.create_index("ix_hr_crews_project_id", "hr_crews", ["project_id"])

    op.create_table(
        "hr_crew_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("crew_id", sa.Integer(), sa.ForeignKey("hr_crews.id"), nullable=False),
        sa.Column("personnel_id", sa.Integer(), sa.ForeignKey("hr_personnel.id"), nullable=False),
        sa.Column("deployment_id", sa.Integer(), sa.ForeignKey("hr_deployments.id"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_hr_crew_members_crew_id", "hr_crew_members", ["crew_id"])
    op.create_index("ix_hr_crew_members_personnel_id", "hr_crew_members", ["personnel_id"])

    op.create_table(
        "hr_attendance_sheets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("hr_shifts.id"), nullable=False),
        sa.Column("crew_id", sa.Integer(), sa.ForeignKey("hr_crews.id"), nullable=True),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Draft"),
        sa.Column("late", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned', 'Rejected', 'Approved')",
            name="ck_hr_sheet_status",
        ),
    )
    op.create_index("ix_hr_attendance_sheets_organization_id", "hr_attendance_sheets", ["organization_id"])
    op.create_index("ix_hr_attendance_sheets_project_id", "hr_attendance_sheets", ["project_id"])
    op.create_index("ix_hr_attendance_sheets_attendance_date", "hr_attendance_sheets", ["attendance_date"])

    op.create_table(
        "hr_attendance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sheet_id", sa.Integer(), sa.ForeignKey("hr_attendance_sheets.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("personnel_id", sa.Integer(), sa.ForeignKey("hr_personnel.id"), nullable=False),
        sa.Column("deployment_id", sa.Integer(), sa.ForeignKey("hr_deployments.id"), nullable=False),
        sa.Column("shift_id", sa.Integer(), sa.ForeignKey("hr_shifts.id"), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("source", sa.String(40), nullable=False, server_default="Manual"),
        sa.Column("worked_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("regular_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overtime_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("remarks", sa.Text(), nullable=False, server_default=""),
        *_audit_columns(),
        sa.UniqueConstraint("project_id", "personnel_id", "attendance_date", "shift_id", name="uq_hr_attendance_day"),
        sa.CheckConstraint(
            "status IN ('Present', 'Absent', 'On Leave', 'Weekly Off/Holiday', 'Partial Attendance')",
            name="ck_hr_attendance_status",
        ),
        sa.CheckConstraint(
            "source IN ('Manual', 'Excel Import', 'Approved Device/System Integration')",
            name="ck_hr_attendance_source",
        ),
    )
    op.create_index("ix_hr_attendance_sheet_id", "hr_attendance", ["sheet_id"])
    op.create_index("ix_hr_attendance_project_id", "hr_attendance", ["project_id"])
    op.create_index("ix_hr_attendance_personnel_id", "hr_attendance", ["personnel_id"])

    op.create_table(
        "hr_attendance_segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attendance_id", sa.Integer(), sa.ForeignKey("hr_attendance.id"), nullable=False),
        sa.Column("check_in", sa.DateTime(), nullable=False),
        sa.Column("check_out", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_hr_attendance_segments_attendance_id", "hr_attendance_segments", ["attendance_id"])

    op.create_table(
        "hr_attendance_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("attendance_id", sa.Integer(), sa.ForeignKey("hr_attendance.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column("proposed", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Pending Review"),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('Missing punch', 'Attendance dispute', 'Late submission', 'Authorized adjustment')",
            name="ck_hr_correction_kind",
        ),
        sa.CheckConstraint(
            "status IN ('Pending Review', 'Returned', 'Approved', 'Rejected')",
            name="ck_hr_correction_status",
        ),
    )
    op.create_index("ix_hr_attendance_corrections_organization_id", "hr_attendance_corrections", ["organization_id"])
    op.create_index("ix_hr_attendance_corrections_project_id", "hr_attendance_corrections", ["project_id"])
    op.create_index("ix_hr_attendance_corrections_attendance_id", "hr_attendance_corrections", ["attendance_id"])

    op.create_table(
        "hr_attendance_locks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("locked_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reopened_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopen_reason", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_hr_attendance_locks_project_id", "hr_attendance_locks", ["project_id"])

    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
