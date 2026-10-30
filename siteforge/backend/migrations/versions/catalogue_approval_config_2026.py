"""Catalogue approval configuration and specification template version traceability.

Additive only. Apply after explicit approval.
"""

from alembic import op
import sqlalchemy as sa


revision = "catalogue_apprcfg_26"
down_revision = "catalogue_masters_26"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "procurement_catalogue_approval_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("stages", sa.JSON(), nullable=False),
        sa.Column("submitted_status", sa.String(40), nullable=False, server_default="Under Review"),
        sa.Column("approve_permission", sa.String(120), nullable=False, server_default="procurement.catalogue.approve"),
        sa.Column("require_decision_reason", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("decision_reason_min_length", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("enforce_separation_of_duties", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", name="uq_proc_catalogue_approval_org"),
    )
    op.create_index("ix_proc_catalogue_apprcfg_org", "procurement_catalogue_approval_config", ["organization_id"])
    op.add_column(
        "procurement_items",
        sa.Column("specification_template_version", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("procurement_items", "specification_template_version")
    op.drop_index("ix_proc_catalogue_apprcfg_org", table_name="procurement_catalogue_approval_config")
    op.drop_table("procurement_catalogue_approval_config")
