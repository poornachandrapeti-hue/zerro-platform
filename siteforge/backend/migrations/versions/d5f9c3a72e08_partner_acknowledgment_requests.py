"""Partner PO acknowledgment requests with buyer review.

Revision ID: d5f9c3a72e08
Revises: c4e8a2f61d07
"""
from alembic import op
import sqlalchemy as sa
revision = "d5f9c3a72e08"
down_revision = "c4e8a2f61d07"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("partner_po_acknowledgments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("purchase_order_id", sa.Integer(), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("submitted_version", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="Pending"),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("purchase_order_id", "submitted_version", name="uq_partner_po_ack_version"),
        sa.CheckConstraint("state IN ('Pending','Approved','Rejected')", name="ck_partner_ack_state"))
    for col in ("organization_id", "project_id", "company_id", "purchase_order_id"):
        op.create_index(f"ix_partner_po_acknowledgments_{col}", "partner_po_acknowledgments", [col])

def downgrade():
    op.drop_table("partner_po_acknowledgments")
