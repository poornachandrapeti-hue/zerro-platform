"""NCRs, concessions, and quality holds. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "l7b2e5f93d62"
down_revision = "k6a1d4e82c51"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quality_ncrs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("source_kind", sa.String(20), nullable=False),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("quality_construction_requests.id"), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("quality_material_inspections.id"), nullable=True),
        sa.Column("offer_id", sa.Integer(), sa.ForeignKey("quality_offers.id"), nullable=True),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("location", sa.String(200), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("requirement", sa.Text(), nullable=False, server_default=""),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("affected_scope", sa.Text(), nullable=False, server_default=""),
        sa.Column("containment", sa.Text(), nullable=False, server_default=""),
        sa.Column("raised_on", sa.Date(), nullable=False),
        sa.Column("target_on", sa.Date(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False, server_default=""),
        sa.Column("corrective_action", sa.Text(), nullable=False, server_default=""),
        sa.Column("disposition", sa.String(20), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("verification", sa.Text(), nullable=False, server_default=""),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_quality_ncr_number"),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', "
            "'Cancelled', 'Pending Verification', 'Verification Returned', 'Closed')",
            name="ck_quality_ncr_status",
        ),
        sa.CheckConstraint("severity IN ('Minor', 'Major', 'Critical')", name="ck_quality_ncr_severity"),
        sa.CheckConstraint(
            "disposition IN ('Rework', 'Repair', 'Reject/Return', 'Use-As-Is')",
            name="ck_quality_ncr_disposition",
        ),
        sa.CheckConstraint(
            "source_kind IN ('activity', 'request', 'material', 'offer')",
            name="ck_quality_ncr_source",
        ),
    )
    op.create_index("ix_quality_ncrs_project_id", "quality_ncrs", ["project_id"])
    op.create_table(
        "quality_concessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("ncr_id", sa.Integer(), sa.ForeignKey("quality_ncrs.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("proposal", sa.Text(), nullable=False, server_default=""),
        sa.Column("technical_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_quality_concession_number"),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Cancelled')",
            name="ck_quality_concession_status",
        ),
    )
    op.create_index("ix_quality_concessions_project_id", "quality_concessions", ["project_id"])
    op.create_index("ix_quality_concessions_ncr_id", "quality_concessions", ["ncr_id"])
    op.create_table(
        "quality_holds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("scope_kind", sa.String(20), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=True),
        sa.Column("receipt_line_id", sa.Integer(), sa.ForeignKey("goods_receipt_lines.id"), nullable=True),
        sa.Column("checkpoint_id", sa.Integer(), sa.ForeignKey("quality_checkpoints.id"), nullable=True),
        sa.Column("ncr_id", sa.Integer(), sa.ForeignKey("quality_ncrs.id"), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="Active"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("conditions", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("blocks_issue", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("blocks_work", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("blocks_handover", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("released_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("released_on", sa.Date(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_quality_hold_number"),
        sa.CheckConstraint(
            "status IN ('Active', 'Pending Release', 'Release Returned', 'Released')",
            name="ck_quality_hold_status",
        ),
        sa.CheckConstraint("scope_kind IN ('package', 'activity', 'receipt')", name="ck_quality_hold_scope"),
    )
    op.create_index("ix_quality_holds_project_id", "quality_holds", ["project_id"])


def downgrade():
    pass
