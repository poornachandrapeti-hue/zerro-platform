"""HR deployments, onboarding checks, and workforce requests. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "x2b6c9d37e14"
down_revision = "w1a5f8c26b93"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hr_deployments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("personnel_id", sa.Integer(), sa.ForeignKey("hr_personnel.id"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=True),
        sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("hr_personnel.id"), nullable=True),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("planned_start", sa.Date(), nullable=False),
        sa.Column("planned_end", sa.Date(), nullable=True),
        sa.Column("actual_start", sa.Date(), nullable=True),
        sa.Column("actual_end", sa.Date(), nullable=True),
        sa.Column("shift", sa.String(80), nullable=False, server_default=""),
        sa.Column("required_skills", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="Proposed"),
        sa.Column("status_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('Proposed', 'Pending Approval', 'Approved for Mobilization', 'Mobilized', 'Temporarily Unavailable', 'Demobilized', 'Cancelled')",
            name="ck_hr_deployment_status",
        ),
    )
    op.create_index("ix_hr_deployments_organization_id", "hr_deployments", ["organization_id"])
    op.create_index("ix_hr_deployments_project_id", "hr_deployments", ["project_id"])
    op.create_index("ix_hr_deployments_personnel_id", "hr_deployments", ["personnel_id"])
    op.create_table(
        "hr_onboarding_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("deployment_id", sa.Integer(), sa.ForeignKey("hr_deployments.id"), nullable=False),
        sa.Column("check_type", sa.String(40), nullable=False),
        sa.Column("owner", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Pending"),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("verified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("deployment_id", "check_type", name="uq_hr_onboarding_check"),
        sa.CheckConstraint("status IN ('Pending', 'Verified', 'Not required')", name="ck_hr_onboarding_status"),
    )
    op.create_index("ix_hr_onboarding_checks_deployment_id", "hr_onboarding_checks", ["deployment_id"])
    op.create_table(
        "hr_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=True),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("trade_id", sa.Integer(), sa.ForeignKey("hr_masters.id"), nullable=False),
        sa.Column("headcount", sa.Integer(), nullable=False),
        sa.Column("qualifications", sa.Text(), nullable=False, server_default=""),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("shift", sa.String(80), nullable=False, server_default=""),
        sa.Column("priority", sa.String(20), nullable=False, server_default="Normal"),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False, server_default=""),
        sa.Column("expected_mobilization", sa.Date(), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("status_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_hr_request_number"),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned', 'Rejected', 'Open', 'Partially Allocated', 'Allocated', 'Closed', 'Cancelled')",
            name="ck_hr_request_status",
        ),
        sa.CheckConstraint("priority IN ('Low', 'Normal', 'High', 'Urgent')", name="ck_hr_request_priority"),
        sa.CheckConstraint("headcount > 0", name="ck_hr_request_headcount"),
    )
    op.create_index("ix_hr_requests_organization_id", "hr_requests", ["organization_id"])
    op.create_index("ix_hr_requests_project_id", "hr_requests", ["project_id"])
    op.create_table(
        "hr_request_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("hr_requests.id"), nullable=False),
        sa.Column("personnel_id", sa.Integer(), sa.ForeignKey("hr_personnel.id"), nullable=False),
        sa.Column("deployment_id", sa.Integer(), sa.ForeignKey("hr_deployments.id"), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="Proposed"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("request_id", "personnel_id", name="uq_hr_request_person"),
        sa.CheckConstraint("state IN ('Proposed', 'Allocated', 'Released')", name="ck_hr_request_line_state"),
    )
    op.create_index("ix_hr_request_lines_request_id", "hr_request_lines", ["request_id"])

    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
