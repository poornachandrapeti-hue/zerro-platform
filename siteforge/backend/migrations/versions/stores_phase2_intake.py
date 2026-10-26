"""Stores intake and supplier delivery notices; no stock balance effects."""
import sqlalchemy as sa
from alembic import op
revision = "stores_phase2_intake"
down_revision = "stores_phase1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("stores_delivery_notices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("purchase_order_id", sa.Integer(), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("vendor_company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("number", sa.String(80), nullable=False), sa.Column("number_key", sa.String(80), nullable=False),
        sa.Column("expected_date", sa.Date(), nullable=False),
        sa.Column("delivery_note", sa.String(160), nullable=False, server_default=""),
        sa.Column("lines", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="Submitted"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "number_key", name="uq_stores_asn_project_number"))
    op.create_table("stores_exceptional_intakes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("number", sa.String(80), nullable=False), sa.Column("number_key", sa.String(80), nullable=False),
        sa.Column("intake_type", sa.String(30), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("procurement_warehouses.id"), nullable=False),
        sa.Column("owner_company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("source_company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("lines", sa.JSON(), nullable=False), sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="Pending Review"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("review_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "number_key", name="uq_stores_intake_project_number"))
    for table in ("stores_delivery_notices", "stores_exceptional_intakes"):
        for col in ("organization_id", "project_id"):
            op.create_index(f"ix_{table}_{col}", table, [col])
    op.create_index("ix_stores_delivery_notices_purchase_order_id", "stores_delivery_notices", ["purchase_order_id"])
    op.create_index("ix_stores_delivery_notices_vendor_company_id", "stores_delivery_notices", ["vendor_company_id"])


def downgrade():
    op.drop_table("stores_exceptional_intakes")
    op.drop_table("stores_delivery_notices")
