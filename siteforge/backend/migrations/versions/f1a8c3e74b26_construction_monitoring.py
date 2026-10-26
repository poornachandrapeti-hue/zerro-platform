"""Construction holds and blockers. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "f1a8c3e74b26"
down_revision = "e8c4a1d72f05"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "construction_holds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Open"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("opened_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('Open', 'In Review', 'Returned', 'Rejected', 'Closed')",
            name="ck_construction_hold_status",
        ),
    )
    op.create_index("ix_construction_holds_project_id", "construction_holds", ["project_id"])
    op.create_index("ix_construction_holds_package_id", "construction_holds", ["package_id"])
    op.create_table(
        "construction_blockers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recovery_note", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Open"),
        sa.Column("resolution_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('Delay', 'Obstruction', 'Weather', 'Idle')",
            name="ck_construction_blocker_kind",
        ),
        sa.CheckConstraint(
            "status IN ('Open', 'Resolved')",
            name="ck_construction_blocker_status",
        ),
    )
    op.create_index("ix_construction_blockers_organization_id", "construction_blockers", ["organization_id"])
    op.create_index("ix_construction_blockers_project_id", "construction_blockers", ["project_id"])
    op.create_index("ix_construction_blockers_package_id", "construction_blockers", ["package_id"])


def downgrade():
    pass
