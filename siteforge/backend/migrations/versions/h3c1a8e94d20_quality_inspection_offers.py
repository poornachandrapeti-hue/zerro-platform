"""Inspection offers for verified construction quantity. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "h3c1a8e94d20"
down_revision = "g2b9d4e81c37"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quality_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=False),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=True),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_quality_offer_number"),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled')",
            name="ck_quality_offer_status",
        ),
    )
    op.create_index("ix_quality_offers_organization_id", "quality_offers", ["organization_id"])
    op.create_index("ix_quality_offers_project_id", "quality_offers", ["project_id"])
    op.create_index("ix_quality_offers_package_id", "quality_offers", ["package_id"])
    op.create_table(
        "quality_offer_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("offer_id", sa.Integer(), sa.ForeignKey("quality_offers.id"), nullable=False),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=False),
        sa.Column("offered_quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("offered_percent", sa.Numeric(6, 2), nullable=True),
        sa.Column("accepted_quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("accepted_percent", sa.Numeric(6, 2), nullable=True),
        sa.UniqueConstraint("offer_id", "activity_id", name="uq_quality_offer_activity"),
    )
    op.create_index("ix_quality_offer_lines_offer_id", "quality_offer_lines", ["offer_id"])
    op.create_index("ix_quality_offer_lines_activity_id", "quality_offer_lines", ["activity_id"])

    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
