"""stock ledger for accepted goods receipts"""

import sqlalchemy as sa
from alembic import op

revision = "c4b8e2a91d17"
down_revision = "a9e2c4b71d08"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stock_balances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("procurement_warehouses.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("procurement_items.id"), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False, server_default=""),
        sa.Column("on_hand", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("reserved", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("project_id", "warehouse_id", "item_id", name="uq_stock_balance_item"),
    )
    op.create_index("ix_stock_balances_project_id", "stock_balances", ["project_id"])
    op.create_table(
        "stock_postings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("procurement_warehouses.id"), nullable=False),
        sa.Column("goods_receipt_id", sa.Integer(), sa.ForeignKey("goods_receipts.id"), nullable=True),
        sa.Column("source_posting_id", sa.Integer(), sa.ForeignKey("stock_postings.id"), nullable=True),
        sa.Column("number", sa.String(80), nullable=False),
        sa.Column("number_key", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Posted"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("recipient", sa.String(200), nullable=False, server_default=""),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_stock_posting_number"),
    )
    op.create_index("ix_stock_postings_project_id", "stock_postings", ["project_id"])
    op.create_table(
        "stock_posting_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("posting_id", sa.Integer(), sa.ForeignKey("stock_postings.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("procurement_items.id"), nullable=False),
        sa.Column("goods_receipt_line_id", sa.Integer(), sa.ForeignKey("goods_receipt_lines.id"), nullable=True),
        sa.Column("source_line_id", sa.Integer(), sa.ForeignKey("stock_posting_lines.id"), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
    )
    op.create_index("ix_stock_posting_lines_posting_id", "stock_posting_lines", ["posting_id"])
    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
