"""Stock reservations and issues for a work package.

Revision ID: e3c9e5a74b12
Revises: e2b8d4f63a01
"""
from alembic import op
import sqlalchemy as sa

revision = "e3c9e5a74b12"
down_revision = "e2b8d4f63a01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "stock_postings",
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
    )
    op.create_index("ix_stock_postings_package_id", "stock_postings", ["package_id"])


def downgrade():
    op.drop_index("ix_stock_postings_package_id", table_name="stock_postings")
    op.drop_column("stock_postings", "package_id")
