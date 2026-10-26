"""procurement master data, requirements, and requisitions"""

import sqlalchemy as sa
from alembic import op

revision = "b4d9e2c71a06"
down_revision = "a1c7e4b92d08"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "procurement_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("code_key", sa.String(80), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("discipline_ids", sa.JSON(), nullable=False),
        sa.Column("specification", sa.Text(), nullable=False, server_default=""),
        sa.Column("size_rating", sa.String(120), nullable=False, server_default=""),
        sa.Column("base_unit", sa.String(20), nullable=False),
        sa.Column("approved_make", sa.String(200), nullable=False, server_default=""),
        sa.Column("inspection_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tracking_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "code_key", name="uq_procurement_items_code"),
    )
    op.create_index("ix_procurement_items_organization_id", "procurement_items", ["organization_id"])
    op.create_table(
        "procurement_conversions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("from_unit", sa.String(20), nullable=False),
        sa.Column("to_unit", sa.String(20), nullable=False),
        sa.Column("factor", sa.Numeric(14, 6), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "from_unit", "to_unit", name="uq_procurement_conversions"),
    )
    op.create_index("ix_procurement_conversions_organization_id", "procurement_conversions", ["organization_id"])
    op.create_table(
        "procurement_vendors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("code_key", sa.String(80), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("categories", sa.Text(), nullable=False, server_default=""),
        sa.Column("contact_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("email", sa.String(254), nullable=False, server_default=""),
        sa.Column("phone", sa.String(40), nullable=False, server_default=""),
        sa.Column("address", sa.Text(), nullable=False, server_default=""),
        sa.Column("tax_details", sa.Text(), nullable=False, server_default=""),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="Pending"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "code_key", name="uq_procurement_vendors_code"),
    )
    op.create_index("ix_procurement_vendors_organization_id", "procurement_vendors", ["organization_id"])
    op.create_table(
        "procurement_warehouses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("code_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("location", sa.String(200), nullable=False, server_default=""),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("officer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "code_key", name="uq_procurement_warehouses_code"),
    )
    op.create_index("ix_procurement_warehouses_project_id", "procurement_warehouses", ["project_id"])
    op.create_table(
        "material_requirements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("number", sa.String(80), nullable=False),
        sa.Column("number_key", sa.String(80), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=False),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("required_date", sa.Date(), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default="Normal"),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=False, server_default=""),
        sa.Column("drawing_id", sa.Integer(), sa.ForeignKey("drawings.id"), nullable=True),
        sa.Column("drawing_revision_id", sa.Integer(), sa.ForeignKey("drawing_revisions.id"), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("impact_state", sa.String(40), nullable=False, server_default=""),
        sa.Column("impact_detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("impact_decision", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_material_requirements_number"),
    )
    op.create_index("ix_material_requirements_project_id", "material_requirements", ["project_id"])
    op.create_table(
        "material_requirement_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("material_requirements.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("procurement_items.id"), nullable=False),
        sa.Column("specification", sa.Text(), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("required_date", sa.Date(), nullable=False),
        sa.Column("tag", sa.String(80), nullable=False, server_default=""),
        sa.Column("engineering_reference", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_material_requirement_lines_requirement_id", "material_requirement_lines", ["requirement_id"])
    op.create_table(
        "purchase_requisitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("number", sa.String(80), nullable=False),
        sa.Column("number_key", sa.String(80), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_date", sa.Date(), nullable=False),
        sa.Column("required_delivery", sa.Date(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_purchase_requisitions_number"),
    )
    op.create_index("ix_purchase_requisitions_project_id", "purchase_requisitions", ["project_id"])
    op.create_table(
        "purchase_requisition_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requisition_id", sa.Integer(), sa.ForeignKey("purchase_requisitions.id"), nullable=False),
        sa.Column("requirement_line_id", sa.Integer(), sa.ForeignKey("material_requirement_lines.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("procurement_items.id"), nullable=False),
        sa.Column("specification", sa.Text(), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("estimated_price", sa.Numeric(14, 2), nullable=True),
    )
    op.create_index("ix_purchase_requisition_lines_requisition_id", "purchase_requisition_lines", ["requisition_id"])
    op.create_index(
        "ix_purchase_requisition_lines_requirement_line_id",
        "purchase_requisition_lines",
        ["requirement_line_id"],
    )
    op.create_table(
        "procurement_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("resource", sa.String(40), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("stored_files.id"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_procurement_files_resource_id", "procurement_files", ["resource_id"])
    op.create_table(
        "procurement_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("resource", sa.String(40), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_procurement_events_resource_id", "procurement_events", ["resource_id"])
    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    op.drop_table("procurement_events")
    op.drop_table("procurement_files")
    op.drop_table("purchase_requisition_lines")
    op.drop_table("purchase_requisitions")
    op.drop_table("material_requirement_lines")
    op.drop_table("material_requirements")
    op.drop_table("procurement_warehouses")
    op.drop_table("procurement_vendors")
    op.drop_table("procurement_conversions")
    op.drop_table("procurement_items")
