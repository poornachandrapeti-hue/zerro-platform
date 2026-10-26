"""Quality dossiers and punch items. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "n9d4a7b15e84"
down_revision = "m8c3f6a04e73"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quality_punches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=False),
        sa.Column("blocker_id", sa.Integer(), sa.ForeignKey("construction_blockers.id"), nullable=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=True),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("issue_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="Open"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("verification", sa.Text(), nullable=False, server_default=""),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_quality_punch_number"),
        sa.CheckConstraint("issue_type IN ('Observation', 'Punch')", name="ck_quality_punch_type"),
        sa.CheckConstraint("severity IN ('Minor', 'Major', 'Critical')", name="ck_quality_punch_severity"),
        sa.CheckConstraint(
            "status IN ('Open', 'Pending Closure', 'Closure Returned', 'Closed', 'Cancelled')",
            name="ck_quality_punch_status",
        ),
    )
    op.create_index("ix_quality_punches_project_id", "quality_punches", ["project_id"])
    op.create_table(
        "quality_dossiers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_quality_dossier_number"),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled')",
            name="ck_quality_dossier_status",
        ),
    )
    op.create_index("ix_quality_dossiers_project_id", "quality_dossiers", ["project_id"])


def downgrade():
    pass
