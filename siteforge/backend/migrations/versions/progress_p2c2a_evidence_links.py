"""P2C2A persisted Construction / QA evidence proposals and review history."""
from alembic import op
import sqlalchemy as sa

revision = "progress_p2c2a_evidence_links"
down_revision = "equipment_e7b3_handoffs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "progress_evidence_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("progress_reports.id"), nullable=False),
        sa.Column("progress_line_id", sa.Integer(), sa.ForeignKey("progress_lines.id"), nullable=False),
        sa.Column("inspection_request_id", sa.Integer(), sa.ForeignKey("quality_construction_requests.id"), nullable=False),
        sa.Column("accepted_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("binding_evidence_ref", sa.String(240), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Proposed"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("review_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("organization_id", "project_id", "progress_line_id", "inspection_request_id", name="uq_progress_evidence_pair"),
        sa.CheckConstraint("status IN ('Proposed', 'Approved', 'Rejected', 'Revoked')", name="ck_progress_evidence_link_status"),
        sa.CheckConstraint("accepted_quantity >= 0", name="ck_progress_evidence_accepted_qty"),
    )
    for key in ("organization_id", "project_id", "progress_line_id", "inspection_request_id"):
        op.create_index(f"ix_progress_evidence_{key}", "progress_evidence_links", [key])
    op.create_table(
        "progress_evidence_link_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("link_id", sa.Integer(), sa.ForeignKey("progress_evidence_links.id"), nullable=False),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("action IN ('Proposed', 'Approved', 'Rejected', 'Revoked')", name="ck_progress_evidence_link_action"),
    )
    op.create_index("ix_progress_evidence_event_link", "progress_evidence_link_events", ["link_id"])


def downgrade():
    op.drop_index("ix_progress_evidence_event_link", "progress_evidence_link_events")
    op.drop_table("progress_evidence_link_events")
    for key in ("organization_id", "project_id", "progress_line_id", "inspection_request_id"):
        op.drop_index(f"ix_progress_evidence_{key}", "progress_evidence_links")
    op.drop_table("progress_evidence_links")
