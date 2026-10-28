"""Append-only catalogue item specification history."""
from alembic import op
import sqlalchemy as sa

revision = "catalogue_hist_26"
down_revision = "catalogue_appr_26"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "procurement_item_specification_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("procurement_items.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("item_version", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("item_id", "sequence", name="uq_procurement_item_spec_history_sequence"),
    )
    op.create_index("ix_proc_item_spec_hist_org", "procurement_item_specification_history", ["organization_id"])
    op.create_index("ix_proc_item_spec_hist_item", "procurement_item_specification_history", ["item_id"])


def downgrade():
    op.drop_index("ix_proc_item_spec_hist_item", table_name="procurement_item_specification_history")
    op.drop_index("ix_proc_item_spec_hist_org", table_name="procurement_item_specification_history")
    op.drop_table("procurement_item_specification_history")
