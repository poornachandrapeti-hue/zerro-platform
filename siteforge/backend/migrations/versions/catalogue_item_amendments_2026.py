"""Controlled amendments to approved procurement items."""
from alembic import op
import sqlalchemy as sa

revision = "catalogue_amend_26"
down_revision = "catalogue_hist_26"  # MUST reconcile against actual Alembic graph before deployment
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("procurement_item_amendments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("procurement_items.id"), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column("proposed", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_proc_item_amend_org", "procurement_item_amendments", ["organization_id"])
    op.create_index("ix_proc_item_amend_item", "procurement_item_amendments", ["item_id"])
    # PostgreSQL only: at most one pending amendment for each catalogue item.
    op.create_index("uq_proc_item_pending_amendment", "procurement_item_amendments",
                    ["item_id"], unique=True, postgresql_where=sa.text("status = 'Pending Approval'"))


def downgrade():
    op.drop_index("uq_proc_item_pending_amendment", table_name="procurement_item_amendments")
    op.drop_index("ix_proc_item_amend_item", table_name="procurement_item_amendments")
    op.drop_index("ix_proc_item_amend_org", table_name="procurement_item_amendments")
    op.drop_table("procurement_item_amendments")
