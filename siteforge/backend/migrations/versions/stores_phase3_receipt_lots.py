"""Stores receipt-lot provenance without duplicating physical ledger."""
from alembic import op
import sqlalchemy as sa

revision = "stores_phase3_receipt_lots"
down_revision = "stores_phase3_inspection_tracking"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("stores_receipt_lots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("organization_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("goods_receipt_line_id", sa.Integer, sa.ForeignKey("goods_receipt_lines.id"), nullable=False),
        sa.Column("warehouse_id", sa.Integer, sa.ForeignKey("procurement_warehouses.id"), nullable=False),
        sa.Column("location_id", sa.Integer, sa.ForeignKey("stores_locations.id")),
        sa.Column("owner_company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("custodian_company_id", sa.Integer, sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("lot_code", sa.String(100), nullable=False),
        sa.Column("batch_number", sa.String(100), nullable=False, server_default=""),
        sa.Column("heat_number", sa.String(100), nullable=False, server_default=""),
        sa.Column("serial_number", sa.String(100), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(14,3), nullable=False),
        sa.Column("expiry_date", sa.Date),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("goods_receipt_line_id", "lot_code", name="uq_stores_receipt_line_lot"),
        sa.CheckConstraint("quantity > 0", name="ck_stores_receipt_lot_positive"))
    for col in ("organization_id", "project_id", "goods_receipt_line_id"):
        op.create_index("ix_stores_receipt_lots_" + col, "stores_receipt_lots", [col])

def downgrade():
    op.drop_table("stores_receipt_lots")
