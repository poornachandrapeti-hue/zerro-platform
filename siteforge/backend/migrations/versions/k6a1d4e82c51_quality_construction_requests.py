"""Construction inspection requests. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "k6a1d4e82c51"
down_revision = "j5f3b8c27e40"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quality_construction_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=False),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("quality_forms.id"), nullable=False),
        sa.Column("checkpoint_id", sa.Integer(), sa.ForeignKey("quality_checkpoints.id"), nullable=True),
        sa.Column("follows_id", sa.Integer(), sa.ForeignKey("quality_construction_requests.id"), nullable=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("outcome", sa.String(40), nullable=False, server_default="Pending"),
        sa.Column("location", sa.String(200), nullable=False, server_default=""),
        sa.Column("requested_on", sa.Date(), nullable=False),
        sa.Column("requester_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("inspector_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("attendees", sa.Text(), nullable=False, server_default=""),
        sa.Column("findings", sa.Text(), nullable=False, server_default=""),
        sa.Column("offered_quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("offered_percent", sa.Numeric(8, 2), nullable=True),
        sa.Column("accepted_quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("accepted_percent", sa.Numeric(8, 2), nullable=True),
        sa.Column("rejected_quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_quality_construction_number"),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled')",
            name="ck_quality_construction_status",
        ),
        sa.CheckConstraint(
            "outcome IN ('Pending', 'Accepted', 'Partially Accepted', 'Rejected')",
            name="ck_quality_construction_outcome",
        ),
    )
    op.create_index("ix_quality_construction_requests_project_id", "quality_construction_requests", ["project_id"])
    op.create_index("ix_quality_construction_requests_activity_id", "quality_construction_requests", ["activity_id"])
    op.create_table(
        "quality_construction_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("quality_construction_requests.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("item", sa.String(300), nullable=False),
        sa.Column("result", sa.String(20), nullable=False, server_default=""),
        sa.Column("measurement", sa.String(80), nullable=False, server_default=""),
        sa.UniqueConstraint("request_id", "position", name="uq_quality_construction_result"),
        sa.CheckConstraint(
            "result IN ('', 'Pass', 'Fail', 'Not applicable')",
            name="ck_quality_construction_result",
        ),
    )
    op.create_index("ix_quality_construction_results_request_id", "quality_construction_results", ["request_id"])


def downgrade():
    pass
