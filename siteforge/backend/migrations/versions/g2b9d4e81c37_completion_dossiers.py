"""Completion dossiers for construction handover. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "g2b9d4e81c37"
down_revision = "f1a8c3e74b26"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "completion_dossiers",
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
        sa.UniqueConstraint("project_id", "number_key", name="uq_completion_dossier_number"),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled')",
            name="ck_completion_dossier_status",
        ),
    )
    op.create_index("ix_completion_dossiers_organization_id", "completion_dossiers", ["organization_id"])
    op.create_index("ix_completion_dossiers_project_id", "completion_dossiers", ["project_id"])
    op.create_index("ix_completion_dossiers_package_id", "completion_dossiers", ["package_id"])


def downgrade():
    pass
