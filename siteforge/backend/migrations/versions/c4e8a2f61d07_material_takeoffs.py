"""Material take-offs from drawing revisions, requirement line trace and stock allocations. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "c4e8a2f61d07"
down_revision = "b7d3e9a15c28"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "material_takeoffs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("drawing_id", sa.Integer(), sa.ForeignKey("drawings.id"), nullable=False),
        sa.Column("revision_id", sa.Integer(), sa.ForeignKey("drawing_revisions.id"), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=False),
        sa.Column("number", sa.String(80), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("pages", sa.String(80), nullable=False, server_default=""),
        sa.Column("dedupe_key", sa.String(120), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="Draft"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("return_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("previous_id", sa.Integer(), sa.ForeignKey("material_takeoffs.id"), nullable=True),
        sa.Column("change_state", sa.String(30), nullable=False, server_default=""),
        sa.Column("change_summary", sa.JSON(), nullable=True),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("revision_id", "dedupe_key", name="uq_takeoff_source"),
    )
    for column in ("organization_id", "project_id", "drawing_id", "revision_id", "discipline_id"):
        op.create_index(f"ix_material_takeoffs_{column}", "material_takeoffs", [column])

    op.create_table(
        "material_takeoff_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("takeoff_id", sa.Integer(), sa.ForeignKey("material_takeoffs.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("specification", sa.Text(), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("unit", sa.String(20), nullable=False, server_default=""),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("procurement_items.id"), nullable=True),
        sa.Column("reference", sa.String(80), nullable=False, server_default=""),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("table_ref", sa.String(40), nullable=False, server_default=""),
        sa.Column("row_ref", sa.String(40), nullable=False, server_default=""),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("flags", sa.JSON(), nullable=True),
        sa.Column("origin", sa.String(20), nullable=False, server_default="Added"),
        sa.Column("original", sa.JSON(), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_material_takeoff_lines_takeoff_id", "material_takeoff_lines", ["takeoff_id"])

    op.create_table(
        "material_takeoff_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("takeoff_id", sa.Integer(), sa.ForeignKey("material_takeoffs.id"), nullable=False),
        sa.Column("line_id", sa.Integer(), sa.ForeignKey("material_takeoff_lines.id"), nullable=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("field", sa.String(40), nullable=False, server_default=""),
        sa.Column("old_value", sa.Text(), nullable=False, server_default=""),
        sa.Column("new_value", sa.Text(), nullable=False, server_default=""),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_material_takeoff_corrections_takeoff_id", "material_takeoff_corrections", ["takeoff_id"]
    )

    op.create_table(
        "material_extraction_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("takeoff_id", sa.Integer(), sa.ForeignKey("material_takeoffs.id"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False, server_default="native-pdf"),
        sa.Column("status", sa.String(20), nullable=False, server_default="Queued"),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_material_extraction_jobs_takeoff_id", "material_extraction_jobs", ["takeoff_id"])

    op.add_column(
        "material_requirements",
        sa.Column("source", sa.String(20), nullable=False, server_default="Manual"),
    )
    op.add_column(
        "material_requirements",
        sa.Column("takeoff_id", sa.Integer(), sa.ForeignKey("material_takeoffs.id"), nullable=True),
    )
    op.create_index("ix_material_requirements_takeoff_id", "material_requirements", ["takeoff_id"])
    op.add_column(
        "material_requirement_lines",
        sa.Column(
            "takeoff_line_id", sa.Integer(), sa.ForeignKey("material_takeoff_lines.id"), nullable=True
        ),
    )
    op.add_column(
        "material_requirement_lines",
        sa.Column(
            "drawing_revision_id", sa.Integer(), sa.ForeignKey("drawing_revisions.id"), nullable=True
        ),
    )
    op.create_index(
        "ix_material_requirement_lines_takeoff_line_id", "material_requirement_lines", ["takeoff_line_id"]
    )

    op.create_table(
        "fulfilment_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "requirement_line_id",
            sa.Integer(),
            sa.ForeignKey("material_requirement_lines.id"),
            nullable=False,
        ),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("procurement_items.id"), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("procurement_warehouses.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Active"),
        sa.Column("release_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("released_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in ("organization_id", "project_id", "requirement_line_id", "item_id"):
        op.create_index(f"ix_fulfilment_allocations_{column}", "fulfilment_allocations", [column])


def downgrade():
    pass
