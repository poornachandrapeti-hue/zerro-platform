"""Organization-scoped catalogue specification templates."""
from alembic import op
import sqlalchemy as sa
revision = "catalogue_cfg_26"
down_revision = "catalogue_specs_26"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("procurement_specification_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("discipline", sa.String(100), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "discipline", "category"))
    op.create_index("ix_procurement_spec_templates_org", "procurement_specification_templates", ["organization_id"])

def downgrade():
    op.drop_index("ix_procurement_spec_templates_org", "procurement_specification_templates")
    op.drop_table("procurement_specification_templates")
