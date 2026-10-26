"""Add QA-controlled tracking without duplicating existing procurement stock ledger."""
import sqlalchemy as sa
from alembic import op
revision = "stores_phase3_inspection_tracking"
down_revision = "stores_phase2_evidence"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("stores_inspection_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("goods_receipt_line_id", sa.Integer(), sa.ForeignKey("goods_receipt_lines.id"), nullable=False, unique=True),
        sa.Column("pending_qty", sa.Numeric(14,3), nullable=False),
        sa.Column("accepted_qty", sa.Numeric(14,3), nullable=False, server_default="0"),
        sa.Column("rejected_qty", sa.Numeric(14,3), nullable=False, server_default="0"),
        sa.Column("quarantined_qty", sa.Numeric(14,3), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="Pending Inspection"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_stores_inspection_cases_project_id", "stores_inspection_cases", ["project_id"])
    op.create_index("ix_stores_inspection_cases_organization_id", "stores_inspection_cases", ["organization_id"])
    op.create_table("stores_inspection_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("stores_inspection_cases.id"), nullable=False),
        sa.Column("disposition", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(14,3), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_stores_inspection_decision_retry"))
    op.create_index("ix_stores_inspection_decisions_case_id", "stores_inspection_decisions", ["case_id"])


def downgrade():
    op.drop_table("stores_inspection_decisions")
    op.drop_table("stores_inspection_cases")
