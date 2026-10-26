"""Work-package release state and readiness checks. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "c5e8a1d94b27"
down_revision = "a8d4c2e91b36"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "work_packages",
        sa.Column("release_state", sa.String(30), nullable=False, server_default="Not Submitted"),
    )
    op.create_check_constraint(
        "ck_work_package_release_state",
        "work_packages",
        "release_state IN ('Not Submitted', 'In Review', 'Returned', 'Rejected', 'Released')",
    )
    op.create_table(
        "construction_readiness",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=False),
        sa.Column("check_type", sa.String(40), nullable=False),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("source_label", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("required_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Not Checked"),
        sa.Column("verified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("package_id", "check_type", name="uq_construction_readiness_type"),
        sa.CheckConstraint(
            "check_type IN ('Drawing', 'Material', 'Predecessor', 'Workfront', 'Manpower', "
            "'Procedure', 'Inspection', 'Permit', 'Quality hold')",
            name="ck_construction_readiness_type",
        ),
        sa.CheckConstraint(
            "classification IN ('Mandatory', 'Advisory')",
            name="ck_construction_readiness_class",
        ),
        sa.CheckConstraint(
            "status IN ('Not Checked', 'Pending', 'Satisfied', 'Blocked')",
            name="ck_construction_readiness_status",
        ),
    )
    op.create_index("ix_construction_readiness_package_id", "construction_readiness", ["package_id"])
    op.create_table(
        "construction_release_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_construction_release_snapshots_package_id",
        "construction_release_snapshots",
        ["package_id"],
    )


def downgrade():
    pass
