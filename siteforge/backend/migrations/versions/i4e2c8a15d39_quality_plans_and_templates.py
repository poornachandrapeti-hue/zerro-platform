"""Quality plans, ITP checkpoints, and inspection templates. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "i4e2c8a15d39"
down_revision = "h3c1a8e94d20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quality_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("revision_label", sa.String(20), nullable=False),
        sa.Column("revision_key", sa.String(20), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("engineering_reference", sa.Text(), nullable=False, server_default=""),
        sa.Column("applicable_activities", sa.Text(), nullable=False, server_default=""),
        sa.Column("template_ids", sa.JSON(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "kind", "number_key", "revision_key", name="uq_quality_document_revision"),
        sa.CheckConstraint(
            "kind IN ('Project Quality Plan', 'ITP', 'Inspection Procedure', 'Test Procedure', 'Acceptance Criteria', 'Checklist', 'Report Template')",
            name="ck_quality_document_kind",
        ),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Superseded', 'Cancelled')",
            name="ck_quality_document_status",
        ),
    )
    op.create_index("ix_quality_documents_organization_id", "quality_documents", ["organization_id"])
    op.create_index("ix_quality_documents_project_id", "quality_documents", ["project_id"])
    op.create_table(
        "quality_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("quality_documents.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("criteria_reference", sa.Text(), nullable=False, server_default=""),
        sa.Column("responsible_parties", sa.Text(), nullable=False, server_default=""),
        sa.Column("point_type", sa.String(20), nullable=False),
        sa.Column("notice_hours", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required_evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("required_signatories", sa.Text(), nullable=False, server_default=""),
        sa.Column("partial_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("next_release_conditions", sa.Text(), nullable=False, server_default=""),
        sa.UniqueConstraint("document_id", "sequence", name="uq_quality_checkpoint_sequence"),
        sa.CheckConstraint(
            "point_type IN ('Review', 'Witness', 'Hold', 'Surveillance')",
            name="ck_quality_checkpoint_point",
        ),
    )
    op.create_index("ix_quality_checkpoints_document_id", "quality_checkpoints", ["document_id"])
    op.create_table(
        "quality_forms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("code_key", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("revision_label", sa.String(20), nullable=False),
        sa.Column("revision_key", sa.String(20), nullable=False),
        sa.Column("criteria_document_id", sa.Integer(), sa.ForeignKey("quality_documents.id"), nullable=True),
        sa.Column("units", sa.String(80), nullable=False, server_default=""),
        sa.Column("prerequisites", sa.Text(), nullable=False, server_default=""),
        sa.Column("required_attachments", sa.Text(), nullable=False, server_default=""),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("supersedes_id", sa.Integer(), sa.ForeignKey("quality_forms.id"), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "code_key", "revision_key", name="uq_quality_form_revision"),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Superseded', 'Cancelled')",
            name="ck_quality_form_status",
        ),
    )
    op.create_index("ix_quality_forms_organization_id", "quality_forms", ["organization_id"])
    op.create_index("ix_quality_forms_project_id", "quality_forms", ["project_id"])
    op.create_index("ix_quality_forms_discipline_id", "quality_forms", ["discipline_id"])

    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
