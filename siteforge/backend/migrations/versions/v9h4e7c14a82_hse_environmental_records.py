"""HSE environmental records. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "v9h4e7c14a82"
down_revision = "u8g3d6b03f71"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hse_environment_criteria",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("name_key", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False, server_default=""),
        sa.Column("threshold", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name_key", name="uq_hse_environment_criterion"),
    )
    op.create_index("ix_hse_environment_criteria_project_id", "hse_environment_criteria", ["project_id"])
    op.create_table(
        "hse_environment_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("recorded_on", sa.Date(), nullable=False),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
        sa.Column("criterion_id", sa.Integer(), sa.ForeignKey("hse_environment_criteria.id"), nullable=True),
        sa.Column("reading", sa.Text(), nullable=False, server_default=""),
        sa.Column("result", sa.String(40), nullable=False, server_default="Not assessed"),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("action_id", sa.Integer(), sa.ForeignKey("hse_actions.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_hse_environment_number"),
        sa.CheckConstraint(
            "kind IN ('Waste inspection', 'Spill', 'Dust/noise', 'Discharge check', 'Monitoring evidence')",
            name="ck_hse_environment_kind",
        ),
        sa.CheckConstraint(
            "result IN ('Not assessed', 'Within criteria', 'Outside criteria')",
            name="ck_hse_environment_result",
        ),
    )
    op.create_index("ix_hse_environment_records_project_id", "hse_environment_records", ["project_id"])


def downgrade():
    pass
