"""goods receipts against issued purchase orders"""

import sqlalchemy as sa
from alembic import op

revision = "a9e2c4b71d08"
down_revision = "f3c8a1d74e62"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "purchase_orders",
        sa.Column("closure_reason", sa.Text(), nullable=False, server_default=""),
    )
    op.create_table(
        "goods_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("purchase_order_id", sa.Integer(), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("procurement_warehouses.id"), nullable=True),
        sa.Column("number", sa.String(80), nullable=False),
        sa.Column("number_key", sa.String(80), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("delivery_note", sa.String(200), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="Posted"),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_goods_receipt_number"),
    )
    op.create_index("ix_goods_receipts_project_id", "goods_receipts", ["project_id"])
    op.create_index("ix_goods_receipts_purchase_order_id", "goods_receipts", ["purchase_order_id"])
    op.create_table(
        "goods_receipt_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goods_receipt_id", sa.Integer(), sa.ForeignKey("goods_receipts.id"), nullable=False),
        sa.Column("purchase_order_line_id", sa.Integer(), sa.ForeignKey("purchase_order_lines.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
    )
    op.create_index("ix_goods_receipt_lines_goods_receipt_id", "goods_receipt_lines", ["goods_receipt_id"])
    op.create_index(
        "ix_goods_receipt_lines_purchase_order_line_id",
        "goods_receipt_lines",
        ["purchase_order_line_id"],
    )
    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
