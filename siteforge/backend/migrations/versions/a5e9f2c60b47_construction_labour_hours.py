"""Per-person activity hours on Construction daily lines. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "a5e9f2c60b47"
down_revision = "z4d8e1f59a36"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "progress_labour",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("progress_reports.id"), nullable=False),
        sa.Column("line_id", sa.Integer(), sa.ForeignKey("progress_lines.id"), nullable=False),
        sa.Column("personnel_id", sa.Integer(), sa.ForeignKey("hr_personnel.id"), nullable=False),
        sa.Column("productive_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idle_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idle_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("line_id", "personnel_id", name="uq_progress_labour_person"),
        sa.CheckConstraint("productive_minutes >= 0 AND idle_minutes >= 0", name="ck_progress_labour_minutes"),
        sa.CheckConstraint("productive_minutes + idle_minutes > 0", name="ck_progress_labour_total"),
    )
    op.create_index("ix_progress_labour_report_id", "progress_labour", ["report_id"])
    op.create_index("ix_progress_labour_line_id", "progress_labour", ["line_id"])
    op.create_index("ix_progress_labour_personnel_id", "progress_labour", ["personnel_id"])


def downgrade():
    pass
