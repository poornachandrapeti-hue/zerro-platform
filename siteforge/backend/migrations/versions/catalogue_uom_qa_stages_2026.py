"""Purchase/issue UOM, category QA document packs, and approval reviewer stages.

Additive only. Do not apply without explicit approval.
"""

from alembic import op
import sqlalchemy as sa


revision = "catalogue_uomqa_26"
down_revision = "catalogue_apprcfg_26"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "procurement_items",
        sa.Column("purchase_unit", sa.String(20), nullable=False, server_default=""),
    )
    op.add_column(
        "procurement_items",
        sa.Column("issue_unit", sa.String(20), nullable=False, server_default=""),
    )
    op.add_column(
        "procurement_catalogue_categories",
        sa.Column("qa_document_types", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "procurement_catalogue_approval_config",
        sa.Column("reviewer_stages", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )


def downgrade():
    op.drop_column("procurement_catalogue_approval_config", "reviewer_stages")
    op.drop_column("procurement_catalogue_categories", "qa_document_types")
    op.drop_column("procurement_items", "issue_unit")
    op.drop_column("procurement_items", "purchase_unit")
