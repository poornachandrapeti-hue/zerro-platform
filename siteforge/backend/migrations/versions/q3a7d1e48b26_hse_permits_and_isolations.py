"""HSE permits, isolations, and workfront rules. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "q3a7d1e48b26"
down_revision = "p2f6c9d37a15"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hse_permit_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("name_key", sa.String(80), nullable=False),
        sa.Column("physical_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("handover_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name_key", name="uq_hse_permit_type_name"),
    )
    op.create_index("ix_hse_permit_types_project_id", "hse_permit_types", ["project_id"])
    op.create_table(
        "hse_permits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("type_id", sa.Integer(), sa.ForeignKey("hse_permit_types.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=True),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=True),
        sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("hse_assessments.id"), nullable=True),
        sa.Column("task_description", sa.Text(), nullable=False),
        sa.Column("applicant_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("performing_authority_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("area_owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("issuer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("crew_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("equipment_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("conditions", sa.Text(), nullable=False, server_default=""),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("external_reference", sa.String(80), nullable=False, server_default=""),
        sa.Column("external_evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("work_status", sa.Text(), nullable=False, server_default=""),
        sa.Column("site_condition", sa.Text(), nullable=False, server_default=""),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_hse_permit_number"),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Authorized', 'Active', 'Suspended', 'Expired', 'Closed', 'Cancelled', 'Rejected')",
            name="ck_hse_permit_status",
        ),
    )
    op.create_index("ix_hse_permits_project_id", "hse_permits", ["project_id"])
    op.create_index("ix_hse_permits_package_id", "hse_permits", ["package_id"])
    op.create_table(
        "hse_permit_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("permit_id", sa.Integer(), sa.ForeignKey("hse_permits.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_hse_permit_checks_permit_id", "hse_permit_checks", ["permit_id"])
    op.create_table(
        "hse_permit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("permit_id", sa.Integer(), sa.ForeignKey("hse_permits.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('Extension', 'Revalidation', 'Suspension', 'Activation', 'Handover', 'Condition change', 'Closure', 'Cancellation')",
            name="ck_hse_permit_event_kind",
        ),
    )
    op.create_index("ix_hse_permit_events_permit_id", "hse_permit_events", ["permit_id"])
    op.create_table(
        "hse_isolations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("authority_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Draft"),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("removal_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("allow_removal_with_active_permit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("removed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_hse_isolation_number"),
        sa.CheckConstraint(
            "kind IN ('Isolation Certificate', 'Lockout/Tagout', 'Gas Test', 'Lifting Plan', 'Equipment Check', 'Rescue Arrangement', 'Access Control')",
            name="ck_hse_isolation_kind",
        ),
        sa.CheckConstraint("status IN ('Draft', 'Approved', 'In Force', 'Removed')", name="ck_hse_isolation_status"),
    )
    op.create_index("ix_hse_isolations_project_id", "hse_isolations", ["project_id"])
    op.create_table(
        "hse_permit_isolations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("permit_id", sa.Integer(), sa.ForeignKey("hse_permits.id"), nullable=False),
        sa.Column("isolation_id", sa.Integer(), sa.ForeignKey("hse_isolations.id"), nullable=False),
        sa.UniqueConstraint("permit_id", "isolation_id", name="uq_hse_permit_isolation"),
    )
    op.create_index("ix_hse_permit_isolations_permit_id", "hse_permit_isolations", ["permit_id"])
    op.create_index("ix_hse_permit_isolations_isolation_id", "hse_permit_isolations", ["isolation_id"])
    op.create_table(
        "hse_conflict_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("type_a_id", sa.Integer(), sa.ForeignKey("hse_permit_types.id"), nullable=False),
        sa.Column("type_b_id", sa.Integer(), sa.ForeignKey("hse_permit_types.id"), nullable=False),
        sa.Column("same_area", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("require_decision", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_hse_conflict_rules_project_id", "hse_conflict_rules", ["project_id"])
    op.create_table(
        "hse_coordinations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("permit_id", sa.Integer(), sa.ForeignKey("hse_permits.id"), nullable=False),
        sa.Column("other_permit_id", sa.Integer(), sa.ForeignKey("hse_permits.id"), nullable=False),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("hse_conflict_rules.id"), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False, server_default=""),
        sa.Column("controls", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="Open"),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("permit_id", "other_permit_id", "rule_id", name="uq_hse_coordination"),
    )
    op.create_index("ix_hse_coordinations_project_id", "hse_coordinations", ["project_id"])
    op.create_index("ix_hse_coordinations_permit_id", "hse_coordinations", ["permit_id"])


def downgrade():
    pass
