"""Incoming material inspections. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "j5f3b8c27e40"
down_revision = "i4e2c8a15d39"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quality_material_inspections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("goods_receipt_id", sa.Integer(), sa.ForeignKey("goods_receipts.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("inspector_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("requested_on", sa.Date(), nullable=False),
        sa.Column("inspected_on", sa.Date(), nullable=True),
        sa.Column("certificate_reference", sa.String(200), nullable=False, server_default=""),
        sa.Column("findings", sa.Text(), nullable=False, server_default=""),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_quality_material_number"),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled')",
            name="ck_quality_material_status",
        ),
    )
    op.create_index("ix_quality_material_inspections_project_id", "quality_material_inspections", ["project_id"])
    op.create_index(
        "ix_quality_material_inspections_goods_receipt_id",
        "quality_material_inspections",
        ["goods_receipt_id"],
    )
    op.create_table(
        "quality_material_dispositions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "inspection_id",
            sa.Integer(),
            sa.ForeignKey("quality_material_inspections.id"),
            nullable=False,
        ),
        sa.Column("goods_receipt_line_id", sa.Integer(), sa.ForeignKey("goods_receipt_lines.id"), nullable=False),
        sa.Column("from_state", sa.String(20), nullable=False),
        sa.Column("to_state", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("batch_number", sa.String(80), nullable=False, server_default=""),
        sa.Column("heat_number", sa.String(80), nullable=False, server_default=""),
        sa.Column("serial_number", sa.String(80), nullable=False, server_default=""),
        sa.CheckConstraint("from_state IN ('Pending', 'Quarantined')", name="ck_quality_material_from"),
        sa.CheckConstraint(
            "to_state IN ('Accepted', 'Rejected', 'Quarantined')",
            name="ck_quality_material_to",
        ),
    )
    op.create_index("ix_quality_material_dispositions_inspection_id", "quality_material_dispositions", ["inspection_id"])
    op.create_index(
        "ix_quality_material_dispositions_goods_receipt_line_id",
        "quality_material_dispositions",
        ["goods_receipt_line_id"],
    )


def downgrade():
    pass
