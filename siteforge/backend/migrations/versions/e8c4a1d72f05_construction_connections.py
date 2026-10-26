"""Name an existing stores posting on a daily progress line. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "e8c4a1d72f05"
down_revision = "d6f1a8c24e90"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "progress_lines",
        sa.Column("stock_posting_id", sa.Integer(), sa.ForeignKey("stock_postings.id"), nullable=True),
    )
    op.create_index("ix_progress_lines_stock_posting_id", "progress_lines", ["stock_posting_id"])


def downgrade():
    pass
