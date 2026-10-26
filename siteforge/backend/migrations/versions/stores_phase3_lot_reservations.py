"""Lot-specific reservation register (no stock movements)."""
from alembic import op
import sqlalchemy as sa
revision = "stores_phase3_lot_reservations"
down_revision = "stores_phase3_outbound_lot_allocations"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("stores_lot_reservations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("receipt_lot_id", sa.Integer(), sa.ForeignKey("stores_receipt_lots.id"), nullable=False),
        sa.Column("request_key", sa.String(120), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("remaining_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantity > 0 AND remaining_quantity >= 0 AND remaining_quantity <= quantity", name="ck_stores_lot_reservation_quantities"),
        sa.UniqueConstraint("project_id", "request_key", name="uq_stores_lot_reservation_request"))
    for col in ("organization_id", "project_id", "receipt_lot_id"):
        op.create_index("ix_stores_lot_reservations_" + col, "stores_lot_reservations", [col])

def downgrade():
    op.drop_table("stores_lot_reservations")
