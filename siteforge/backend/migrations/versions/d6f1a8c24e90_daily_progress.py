"""Daily progress reports and milestone weights. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "d6f1a8c24e90"
down_revision = "c5e8a1d94b27"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "activity_milestones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("name_key", sa.String(120), nullable=False),
        sa.Column("weight", sa.Numeric(6, 2), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("activity_id", "name_key", name="uq_activity_milestone_name"),
    )
    op.create_index("ix_activity_milestones_activity_id", "activity_milestones", ["activity_id"])
    op.create_table(
        "progress_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("shift", sa.String(20), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=False),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("site_engineer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("weather", sa.String(120), nullable=False, server_default=""),
        sa.Column("remarks", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_progress_report_number"),
        sa.CheckConstraint("shift IN ('Day', 'Night', 'General')", name="ck_progress_report_shift"),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled')",
            name="ck_progress_report_status",
        ),
    )
    op.create_index("ix_progress_reports_organization_id", "progress_reports", ["organization_id"])
    op.create_index("ix_progress_reports_project_id", "progress_reports", ["project_id"])
    op.create_table(
        "progress_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("progress_reports.id"), nullable=False),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("construction_items.id"), nullable=True),
        sa.Column("milestone_id", sa.Integer(), sa.ForeignKey("activity_milestones.id"), nullable=True),
        sa.Column("reverses_line_id", sa.Integer(), sa.ForeignKey("progress_lines.id"), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("unit", sa.String(40), nullable=False, server_default=""),
        sa.Column("drawing_revision_id", sa.Integer(), sa.ForeignKey("drawing_revisions.id"), nullable=True),
        sa.Column("crew_reference", sa.String(200), nullable=False, server_default=""),
        sa.Column("equipment_hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("material_reference", sa.String(200), nullable=False, server_default=""),
        sa.Column("delay_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("rework", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_progress_lines_report_id", "progress_lines", ["report_id"])
    op.create_index("ix_progress_lines_activity_id", "progress_lines", ["activity_id"])


def downgrade():
    pass
