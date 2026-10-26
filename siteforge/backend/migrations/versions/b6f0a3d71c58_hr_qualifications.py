"""HR qualification types, records, and project requirements. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "b6f0a3d71c58"
down_revision = "a5e9f2c60b47"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hr_credential_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("name_key", sa.String(120), nullable=False),
        sa.Column("owner", sa.String(10), nullable=False),
        sa.Column("requires_expiry", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name_key", name="uq_hr_credential_type_name"),
        sa.CheckConstraint("owner IN ('HR', 'HSE', 'QA/QC')", name="ck_hr_credential_type_owner"),
    )
    op.create_index("ix_hr_credential_types_organization_id", "hr_credential_types", ["organization_id"])

    op.create_table(
        "hr_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("personnel_id", sa.Integer(), sa.ForeignKey("hr_personnel.id"), nullable=False),
        sa.Column("type_id", sa.Integer(), sa.ForeignKey("hr_credential_types.id"), nullable=False),
        sa.Column("certificate_number", sa.String(80), nullable=False, server_default=""),
        sa.Column("certificate_key", sa.String(80), nullable=False, server_default=""),
        sa.Column("issuer", sa.String(200), nullable=False, server_default=""),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("applicable_activities", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(30), nullable=False, server_default="Pending Verification"),
        sa.Column("decision_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("verified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('Pending Verification', 'Verified', 'Rejected', 'Withdrawn')",
            name="ck_hr_credential_status",
        ),
    )
    op.create_index("ix_hr_credentials_organization_id", "hr_credentials", ["organization_id"])
    op.create_index("ix_hr_credentials_personnel_id", "hr_credentials", ["personnel_id"])
    op.create_index("ix_hr_credentials_type_id", "hr_credentials", ["type_id"])

    op.create_table(
        "hr_credential_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("type_id", sa.Integer(), sa.ForeignKey("hr_credential_types.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=True),
        sa.Column("scope_key", sa.String(40), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "type_id", "scope_key", name="uq_hr_credential_rule"),
    )
    op.create_index("ix_hr_credential_rules_organization_id", "hr_credential_rules", ["organization_id"])
    op.create_index("ix_hr_credential_rules_project_id", "hr_credential_rules", ["project_id"])


def downgrade():
    pass
