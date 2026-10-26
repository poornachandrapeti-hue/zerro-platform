"""HSE incidents, near misses, and corrective actions. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "s6e1b4f81d59"
down_revision = "r5d9a3e70c48"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hse_incident_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("name_key", sa.String(80), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name_key", name="uq_hse_incident_category"),
    )
    op.create_index("ix_hse_incident_categories_project_id", "hse_incident_categories", ["project_id"])
    op.create_table(
        "hse_incident_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("severity", sa.String(80), nullable=False),
        sa.Column("severity_key", sa.String(80), nullable=False),
        sa.Column("requires_investigation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "severity_key", name="uq_hse_incident_rule"),
    )
    op.create_index("ix_hse_incident_rules_project_id", "hse_incident_rules", ["project_id"])
    op.create_table(
        "hse_incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("hse_incident_categories.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone_name", sa.String(64), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("location", sa.Text(), nullable=False, server_default=""),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=True),
        sa.Column("involved", sa.Text(), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("immediate_actions", sa.Text(), nullable=False, server_default=""),
        sa.Column("emergency_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("initial_severity", sa.String(80), nullable=False, server_default=""),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("reporter_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("verified_classification", sa.String(80), nullable=False, server_default=""),
        sa.Column("contributing_factors", sa.Text(), nullable=False, server_default=""),
        sa.Column("root_causes", sa.Text(), nullable=False, server_default=""),
        sa.Column("lessons", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="Reported"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_hse_incident_number"),
        sa.CheckConstraint(
            "status IN ('Reported', 'Under Investigation', 'Pending Closure', 'Returned for Correction', 'Closed', 'Cancelled', 'Rejected')",
            name="ck_hse_incident_status",
        ),
    )
    op.create_index("ix_hse_incidents_project_id", "hse_incidents", ["project_id"])
    op.create_table(
        "hse_incident_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("hse_incidents.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("incident_id", "user_id", name="uq_hse_incident_member"),
    )
    op.create_index("ix_hse_incident_members_incident_id", "hse_incident_members", ["incident_id"])
    op.create_table(
        "hse_action_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("effectiveness_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", name="uq_hse_action_rule"),
    )
    op.create_index("ix_hse_action_rules_project_id", "hse_action_rules", ["project_id"])
    op.create_table(
        "hse_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False, server_default=""),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(80), nullable=False, server_default=""),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("verifier_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("interim_controls", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("effectiveness", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="Open"),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_hse_action_number"),
        sa.CheckConstraint(
            "status IN ('Open', 'In Progress', 'Pending Verification', 'Closed', 'Cancelled')",
            name="ck_hse_action_status",
        ),
    )
    op.create_index("ix_hse_actions_project_id", "hse_actions", ["project_id"])


def downgrade():
    pass
