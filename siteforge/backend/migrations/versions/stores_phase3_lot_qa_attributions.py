"""Receipt-line QA-to-lot attribution, no stock movements or implicit release."""
from alembic import op
import sqlalchemy as sa
revision = "stores_phase3_lot_qa_attributions"
down_revision = "stores_phase3_posting_lot_allocations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("stores_lot_qa_attributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("inspection_case_id", sa.Integer(), sa.ForeignKey("stores_inspection_cases.id"), nullable=False),
        sa.Column("receipt_lot_id", sa.Integer(), sa.ForeignKey("stores_receipt_lots.id"), nullable=False),
        sa.Column("disposition", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("case_version_at_entry", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantity > 0", name="ck_stores_lot_qa_positive"),
        sa.CheckConstraint("disposition IN ('Accepted','Rejected','Quarantined')", name="ck_stores_lot_qa_disposition"),
        sa.UniqueConstraint("inspection_case_id", "idempotency_key", name="uq_stores_lot_qa_retry"))
    for c in ("organization_id", "project_id", "inspection_case_id", "receipt_lot_id"):
        op.create_index("ix_stores_lot_qa_attributions_" + c, "stores_lot_qa_attributions", [c])


def downgrade():
    op.drop_table("stores_lot_qa_attributions")
