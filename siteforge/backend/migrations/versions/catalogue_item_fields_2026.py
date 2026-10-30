"""Extend procurement_items with enterprise catalogue identity fields.

Additive only. Does not rename base_unit or replace item IDs.
Apply only after explicit approval and Alembic head reconciliation.
"""

from alembic import op
import sqlalchemy as sa


revision = "catalogue_fields_26"
down_revision = "catalogue_amend_26"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("procurement_items", sa.Column("subcategory", sa.String(120), nullable=False, server_default=""))
    op.add_column("procurement_items", sa.Column("material_grade", sa.String(120), nullable=False, server_default=""))
    op.add_column("procurement_items", sa.Column("applicable_standard", sa.String(200), nullable=False, server_default=""))
    op.add_column("procurement_items", sa.Column("model_number", sa.String(120), nullable=False, server_default=""))
    op.add_column("procurement_items", sa.Column("manufacturer_part_number", sa.String(120), nullable=False, server_default=""))
    op.add_column("procurement_items", sa.Column("hsn_code", sa.String(20), nullable=False, server_default=""))
    op.add_column("procurement_items", sa.Column("mtc_required", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column(
        "procurement_items",
        sa.Column("calibration_certificate_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "procurement_items",
        sa.Column("shelf_life_applicable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("procurement_items", sa.Column("shelf_life_days", sa.Integer(), nullable=True))
    op.add_column(
        "procurement_items",
        sa.Column("preferred_vendor_id", sa.Integer(), sa.ForeignKey("procurement_vendors.id"), nullable=True),
    )
    op.create_index(
        "ix_proc_items_org_mpn",
        "procurement_items",
        ["organization_id", "manufacturer_part_number"],
    )
    op.create_index(
        "ix_proc_items_org_category_sub",
        "procurement_items",
        ["organization_id", "category", "subcategory"],
    )


def downgrade():
    op.drop_index("ix_proc_items_org_category_sub", table_name="procurement_items")
    op.drop_index("ix_proc_items_org_mpn", table_name="procurement_items")
    op.drop_column("procurement_items", "preferred_vendor_id")
    op.drop_column("procurement_items", "shelf_life_days")
    op.drop_column("procurement_items", "shelf_life_applicable")
    op.drop_column("procurement_items", "calibration_certificate_required")
    op.drop_column("procurement_items", "mtc_required")
    op.drop_column("procurement_items", "hsn_code")
    op.drop_column("procurement_items", "manufacturer_part_number")
    op.drop_column("procurement_items", "model_number")
    op.drop_column("procurement_items", "applicable_standard")
    op.drop_column("procurement_items", "material_grade")
    op.drop_column("procurement_items", "subcategory")
