"""HSE induction, toolbox talks, and inspections. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "r5d9a3e70c48"
down_revision = "q3a7d1e48b26"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hse_eligibility_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("category_key", sa.String(80), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=True),
        sa.Column("scope_key", sa.String(40), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "category_key", "scope_key", name="uq_hse_eligibility_rule"),
    )
    op.create_index("ix_hse_eligibility_rules_project_id", "hse_eligibility_rules", ["project_id"])
    op.create_table(
        "hse_eligibility",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("category_key", sa.String(80), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Recorded"),
        sa.Column("verified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawal_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('Recorded', 'Verified', 'Expired', 'Withdrawn')",
            name="ck_hse_eligibility_status",
        ),
    )
    op.create_index("ix_hse_eligibility_project_id", "hse_eligibility", ["project_id"])
    op.create_index("ix_hse_eligibility_member_id", "hse_eligibility", ["member_id"])
    op.create_table(
        "hse_toolbox_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=True),
        sa.Column("scope_key", sa.String(40), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "scope_key", name="uq_hse_toolbox_rule"),
    )
    op.create_index("ix_hse_toolbox_rules_project_id", "hse_toolbox_rules", ["project_id"])
    op.create_table(
        "hse_toolbox_talks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("talk_on", sa.Date(), nullable=False),
        sa.Column("shift", sa.String(40), nullable=False, server_default=""),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=True),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("hse_assessments.id"), nullable=True),
        sa.Column("permit_id", sa.Integer(), sa.ForeignKey("hse_permits.id"), nullable=True),
        sa.Column("presenter_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("issues", sa.Text(), nullable=False, server_default=""),
        sa.Column("follow_up", sa.Text(), nullable=False, server_default=""),
        sa.Column("attachment_reference", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="Draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_hse_toolbox_number"),
        sa.CheckConstraint("status IN ('Draft', 'Held')", name="ck_hse_toolbox_status"),
    )
    op.create_index("ix_hse_toolbox_talks_project_id", "hse_toolbox_talks", ["project_id"])
    op.create_table(
        "hse_toolbox_acks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("talk_id", sa.Integer(), sa.ForeignKey("hse_toolbox_talks.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("talk_id", "member_id", name="uq_hse_toolbox_ack"),
    )
    op.create_index("ix_hse_toolbox_acks_talk_id", "hse_toolbox_acks", ["talk_id"])
    op.create_table(
        "hse_finding_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("severity", sa.String(80), nullable=False),
        sa.Column("severity_key", sa.String(80), nullable=False),
        sa.Column("blocks_work", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "severity_key", name="uq_hse_finding_rule"),
    )
    op.create_index("ix_hse_finding_rules_project_id", "hse_finding_rules", ["project_id"])
    op.create_table(
        "hse_inspections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("inspection_type", sa.String(20), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=True),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=True),
        sa.Column("inspector_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("inspected_on", sa.Date(), nullable=False),
        sa.Column("checklist_document_id", sa.Integer(), sa.ForeignKey("hse_documents.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Recorded"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_hse_inspection_number"),
        sa.CheckConstraint(
            "inspection_type IN ('Routine', 'Workfront', 'Equipment', 'Environmental', 'Other')",
            name="ck_hse_inspection_type",
        ),
        sa.CheckConstraint("status IN ('Draft', 'Recorded')", name="ck_hse_inspection_status"),
    )
    op.create_index("ix_hse_inspections_project_id", "hse_inspections", ["project_id"])
    op.create_table(
        "hse_findings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("inspection_id", sa.Integer(), sa.ForeignKey("hse_inspections.id"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(80), nullable=False),
        sa.Column("severity_key", sa.String(80), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_on", sa.Date(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False, server_default=""),
        sa.Column("photo_reference", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="Open"),
        sa.Column("close_evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("closed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('Open', 'Closed')", name="ck_hse_finding_status"),
    )
    op.create_index("ix_hse_findings_inspection_id", "hse_findings", ["inspection_id"])
    op.create_table(
        "hse_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("observation_type", sa.String(40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("reporter_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Reported"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_hse_observation_number"),
        sa.CheckConstraint(
            "observation_type IN ('Unsafe Condition', 'Unsafe Act', 'Positive Observation', 'Environmental Concern', 'Other')",
            name="ck_hse_observation_type",
        ),
    )
    op.create_index("ix_hse_observations_project_id", "hse_observations", ["project_id"])


def downgrade():
    pass
