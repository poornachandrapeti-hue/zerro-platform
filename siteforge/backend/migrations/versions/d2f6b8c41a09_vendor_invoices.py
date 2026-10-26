"""vendor invoices as procurement evidence, without matching or payment"""

import sqlalchemy as sa
from alembic import op

revision = "d2f6b8c41a09"
down_revision = "c4b8e2a91d17"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vendor_invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("purchase_order_id", sa.Integer(), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("number", sa.String(80), nullable=False),
        sa.Column("number_key", sa.String(80), nullable=False),
        sa.Column("vendor_reference", sa.String(80), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="Draft"),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_vendor_invoice_number"),
    )
    op.create_index("ix_vendor_invoices_project_id", "vendor_invoices", ["project_id"])
    op.create_index("ix_vendor_invoices_purchase_order_id", "vendor_invoices", ["purchase_order_id"])
    op.create_table(
        "vendor_invoice_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("vendor_invoices.id"), nullable=False),
        sa.Column("purchase_order_line_id", sa.Integer(), sa.ForeignKey("purchase_order_lines.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("billed_unit_price", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index("ix_vendor_invoice_lines_invoice_id", "vendor_invoice_lines", ["invoice_id"])
    op.create_index(
        "ix_vendor_invoice_lines_purchase_order_line_id",
        "vendor_invoice_lines",
        ["purchase_order_line_id"],
    )
    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
