"""HSE emergency preparedness. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "u8g3d6b03f71"
down_revision = "t7f2c5a92e60"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hse_emergency_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("procedure", sa.Text(), nullable=False, server_default=""),
        sa.Column("review_days", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", name="uq_hse_emergency_rule"),
    )
    op.create_index("ix_hse_emergency_rules_project_id", "hse_emergency_rules", ["project_id"])
    op.create_table(
        "hse_emergency_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("project_contacts.id"), nullable=False),
        sa.Column("response_role", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Recorded"),
        sa.Column("verified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_due_on", sa.Date(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "contact_id", name="uq_hse_emergency_contact"),
        sa.CheckConstraint("status IN ('Recorded', 'Verified')", name="ck_hse_emergency_contact_status"),
    )
    op.create_index("ix_hse_emergency_contacts_project_id", "hse_emergency_contacts", ["project_id"])
    op.create_table(
        "hse_muster_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("name_key", sa.String(80), nullable=False),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name_key", name="uq_hse_muster_point"),
    )
    op.create_index("ix_hse_muster_points_project_id", "hse_muster_points", ["project_id"])
    op.create_table(
        "hse_emergency_gear",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("name_key", sa.String(80), nullable=False),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("location", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name_key", name="uq_hse_emergency_gear"),
    )
    op.create_index("ix_hse_emergency_gear_project_id", "hse_emergency_gear", ["project_id"])
    op.create_table(
        "hse_emergency_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("engineering_reference", sa.Text(), nullable=False, server_default=""),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("hse_documents.id"), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_hse_emergency_plan"),
    )
    op.create_index("ix_hse_emergency_plans_project_id", "hse_emergency_plans", ["project_id"])
    op.create_table(
        "hse_drills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("planned_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Planned"),
        sa.Column("findings", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_hse_drill_number"),
        sa.CheckConstraint("status IN ('Planned', 'Held', 'Cancelled')", name="ck_hse_drill_status"),
    )
    op.create_index("ix_hse_drills_project_id", "hse_drills", ["project_id"])
    op.create_table(
        "hse_drill_acks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("drill_id", sa.Integer(), sa.ForeignKey("hse_drills.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("drill_id", "member_id", name="uq_hse_drill_ack"),
    )
    op.create_index("ix_hse_drill_acks_drill_id", "hse_drill_acks", ["drill_id"])


def downgrade():
    pass
