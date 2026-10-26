"""Qualifications and calibration. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "m8c3f6a04e73"
down_revision = "l7b2e5f93d62"
branch_labels = None
depends_on = None

_STATUS = (
    "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', "
    "'Rejected', 'Cancelled', 'Withdrawn')"
)


def upgrade():
    op.create_table(
        "quality_qualifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("qualification_type", sa.String(120), nullable=False),
        sa.Column("applicable_activities", sa.Text(), nullable=False, server_default=""),
        sa.Column("issuer", sa.String(200), nullable=False, server_default=""),
        sa.Column("certificate_number", sa.String(80), nullable=False, server_default=""),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("withdrawal_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_quality_qualification_number"),
        sa.CheckConstraint(_STATUS, name="ck_quality_qualification_status"),
    )
    op.create_index("ix_quality_qualifications_project_id", "quality_qualifications", ["project_id"])
    op.create_table(
        "quality_calibrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("equipment_code", sa.String(80), nullable=False),
        sa.Column("description", sa.String(200), nullable=False, server_default=""),
        sa.Column("serial_number", sa.String(80), nullable=False, server_default=""),
        sa.Column("certificate_reference", sa.String(200), nullable=False, server_default=""),
        sa.Column("calibrated_on", sa.Date(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("use_range", sa.String(200), nullable=False, server_default=""),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("withdrawal_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_quality_calibration_number"),
        sa.CheckConstraint(_STATUS, name="ck_quality_calibration_status"),
    )
    op.create_index("ix_quality_calibrations_project_id", "quality_calibrations", ["project_id"])


def downgrade():
    pass
