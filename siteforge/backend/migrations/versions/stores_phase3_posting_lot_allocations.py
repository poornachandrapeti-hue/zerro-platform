"""Explicit allocation to existing posting lines; no duplicate physical stock."""
from alembic import op
import sqlalchemy as sa

revision = "stores_phase3_posting_lot_allocations"
down_revision = "stores_phase3_receipt_lots"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("stores_posting_lot_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("stock_posting_line_id", sa.Integer(), sa.ForeignKey("stock_posting_lines.id"), nullable=False),
        sa.Column("receipt_lot_id", sa.Integer(), sa.ForeignKey("stores_receipt_lots.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantity > 0", name="ck_stores_posting_allocation_positive"),
        sa.UniqueConstraint("stock_posting_line_id", "receipt_lot_id", name="uq_stores_posting_lot_allocation"))
    for name in ("organization_id", "project_id", "stock_posting_line_id", "receipt_lot_id"):
        op.create_index("ix_stores_posting_lot_allocations_" + name, "stores_posting_lot_allocations", [name])

def downgrade():
    op.drop_table("stores_posting_lot_allocations")
