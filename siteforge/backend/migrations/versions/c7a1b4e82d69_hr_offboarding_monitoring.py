"""HR offboarding with checklist and approval, and per-project alert settings. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "c7a1b4e82d69"
down_revision = "b6f0a3d71c58"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hr_offboardings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("deployment_id", sa.Integer(), sa.ForeignKey("hr_deployments.id"), nullable=False),
        sa.Column("personnel_id", sa.Integer(), sa.ForeignKey("hr_personnel.id"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("last_working_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(30), nullable=False, server_default="Draft"),
        sa.Column("status_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Approval', 'Returned', 'Rejected', 'Approved', 'Cancelled')",
            name="ck_hr_offboarding_status",
        ),
    )
    op.create_index("ix_hr_offboardings_organization_id", "hr_offboardings", ["organization_id"])
    op.create_index("ix_hr_offboardings_project_id", "hr_offboardings", ["project_id"])
    op.create_index("ix_hr_offboardings_deployment_id", "hr_offboardings", ["deployment_id"])
    op.create_index("ix_hr_offboardings_personnel_id", "hr_offboardings", ["personnel_id"])

    op.create_table(
        "hr_offboarding_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("offboarding_id", sa.Integer(), sa.ForeignKey("hr_offboardings.id"), nullable=False),
        sa.Column("item", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Pending"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("done_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("offboarding_id", "item", name="uq_hr_offboarding_item"),
        sa.CheckConstraint("status IN ('Pending', 'Done', 'Not applicable')", name="ck_hr_offboarding_item_status"),
    )
    op.create_index("ix_hr_offboarding_items_offboarding_id", "hr_offboarding_items", ["offboarding_id"])

    op.create_table(
        "hr_monitor_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("mobilization_grace_days", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("onboarding_lead_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("attendance_grace_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("escalate_after_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("escalation_user_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", name="uq_hr_monitor_project"),
    )
    op.create_index("ix_hr_monitor_settings_organization_id", "hr_monitor_settings", ["organization_id"])


def downgrade():
    pass
