"""HSE safety holds and controlled restart. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "t7f2c5a92e60"
down_revision = "s6e1b4f81d59"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hse_hold_issuers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "user_id", name="uq_hse_hold_issuer"),
    )
    op.create_index("ix_hse_hold_issuers_project_id", "hse_hold_issuers", ["project_id"])
    op.create_table(
        "hse_hold_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("separate_release", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", name="uq_hse_hold_rule"),
    )
    op.create_index("ix_hse_hold_rules_project_id", "hse_hold_rules", ["project_id"])
    op.create_table(
        "hse_holds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, server_default="Hold"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source", sa.String(80), nullable=False, server_default=""),
        sa.Column("severity", sa.String(80), nullable=False, server_default=""),
        sa.Column("scope_kind", sa.String(20), nullable=False, server_default=""),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=True),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("equipment_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("affected_work", sa.Text(), nullable=False, server_default=""),
        sa.Column("restricted_actions", sa.Text(), nullable=False, server_default=""),
        sa.Column("immediate_controls", sa.Text(), nullable=False, server_default=""),
        sa.Column("release_conditions", sa.Text(), nullable=False, server_default=""),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("issued_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="Reported"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_hse_hold_number"),
        sa.CheckConstraint(
            "status IN ('Reported', 'Active', 'Release Requested', 'Returned', 'Released', 'Rejected')",
            name="ck_hse_hold_status",
        ),
        sa.CheckConstraint(
            "scope_kind IN ('package', 'activity', 'area', 'equipment', 'work', '')",
            name="ck_hse_hold_scope",
        ),
    )
    op.create_index("ix_hse_holds_project_id", "hse_holds", ["project_id"])
    op.create_table(
        "hse_hold_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hold_id", sa.Integer(), sa.ForeignKey("hse_holds.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_hse_hold_events_hold_id", "hse_hold_events", ["hold_id"])


def downgrade():
    pass
