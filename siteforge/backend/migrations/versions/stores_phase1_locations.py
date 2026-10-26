"""Stores Phase 1: scoped warehouse locations; reuse existing procurement_warehouses."""
import sqlalchemy as sa
from alembic import op
revision = "stores_phase1"
down_revision = "cm0122"
branch_labels = None
depends_on = None


def upgrade():
    # Later stores revision ids exceed Alembic's default varchar(32).
    op.alter_column("alembic_version", "version_num", type_=sa.String(128), existing_type=sa.String(32), existing_nullable=False)
    op.create_table("stores_locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), sa.ForeignKey("procurement_warehouses.id"), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("stores_locations.id")),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("code_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("location_type", sa.String(20), nullable=False, server_default="Bin"),
        sa.Column("restrictions", sa.Text(), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("warehouse_id", "code_key", name="uq_stores_locations_warehouse_code"),
        sa.CheckConstraint("location_type IN ('Zone','Rack','Bin')", name="ck_stores_locations_type"),
    )
    for col in ("organization_id", "project_id", "warehouse_id"):
        op.create_index("ix_stores_locations_" + col, "stores_locations", [col])


def downgrade():
    op.drop_table("stores_locations")
