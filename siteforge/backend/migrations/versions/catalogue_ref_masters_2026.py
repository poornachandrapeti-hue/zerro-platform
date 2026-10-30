"""Organization-scoped catalogue reference masters.

Additive only. Does not replace disciplines, vendors, or procurement_items IDs.
Apply only after explicit approval and Alembic head reconciliation.
"""

from alembic import op
import sqlalchemy as sa


revision = "catalogue_masters_26"
down_revision = "catalogue_fields_26"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "procurement_catalogue_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("discipline", sa.String(100), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("name_key", sa.String(120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "discipline", "name_key", name="uq_proc_cat_org_disc_name"),
    )
    op.create_index("ix_proc_cat_org", "procurement_catalogue_categories", ["organization_id"])

    op.create_table(
        "procurement_catalogue_subcategories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("procurement_catalogue_categories.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("name_key", sa.String(120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "category_id", "name_key", name="uq_proc_subcat_org_cat_name"),
    )
    op.create_index("ix_proc_subcat_org", "procurement_catalogue_subcategories", ["organization_id"])
    op.create_index("ix_proc_subcat_category", "procurement_catalogue_subcategories", ["category_id"])

    op.create_table(
        "procurement_uoms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("code_key", sa.String(20), nullable=False),
        sa.Column("name", sa.String(80), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "code_key", name="uq_proc_uom_org_code"),
    )
    op.create_index("ix_proc_uom_org", "procurement_uoms", ["organization_id"])

    op.create_table(
        "procurement_material_grades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("code_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False, server_default=""),
        sa.Column("discipline", sa.String(100), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "code_key", name="uq_proc_grade_org_code"),
    )
    op.create_index("ix_proc_grade_org", "procurement_material_grades", ["organization_id"])

    op.create_table(
        "procurement_standards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("code_key", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "code_key", name="uq_proc_standard_org_code"),
    )
    op.create_index("ix_proc_standard_org", "procurement_standards", ["organization_id"])

    op.create_table(
        "procurement_manufacturers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("code_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "code_key", name="uq_proc_mfr_org_code"),
    )
    op.create_index("ix_proc_mfr_org", "procurement_manufacturers", ["organization_id"])


def downgrade():
    op.drop_index("ix_proc_mfr_org", table_name="procurement_manufacturers")
    op.drop_table("procurement_manufacturers")
    op.drop_index("ix_proc_standard_org", table_name="procurement_standards")
    op.drop_table("procurement_standards")
    op.drop_index("ix_proc_grade_org", table_name="procurement_material_grades")
    op.drop_table("procurement_material_grades")
    op.drop_index("ix_proc_uom_org", table_name="procurement_uoms")
    op.drop_table("procurement_uoms")
    op.drop_index("ix_proc_subcat_category", table_name="procurement_catalogue_subcategories")
    op.drop_index("ix_proc_subcat_org", table_name="procurement_catalogue_subcategories")
    op.drop_table("procurement_catalogue_subcategories")
    op.drop_index("ix_proc_cat_org", table_name="procurement_catalogue_categories")
    op.drop_table("procurement_catalogue_categories")
