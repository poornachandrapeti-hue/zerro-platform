"""HSE controlled references and risk assessments. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "p2f6c9d37a15"
down_revision = "n9d4a7b15e84"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hse_documents",
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
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("applicability", sa.Text(), nullable=False, server_default=""),
        sa.Column("engineering_reference", sa.Text(), nullable=False, server_default=""),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("withdrawal_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "kind", "number_key", "revision_key", name="uq_hse_document_revision"),
        sa.CheckConstraint(
            "kind IN ('HSE Plan', 'Emergency Response Plan', 'Safe Work Procedure', 'Risk Assessment Template', 'Permit Template', 'Inspection Checklist', 'Environmental Control Plan')",
            name="ck_hse_document_kind",
        ),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Superseded', 'Withdrawn')",
            name="ck_hse_document_status",
        ),
    )
    op.create_index("ix_hse_documents_organization_id", "hse_documents", ["organization_id"])
    op.create_index("ix_hse_documents_project_id", "hse_documents", ["project_id"])
    op.create_table(
        "hse_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("number_key", sa.String(40), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=True),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("hse_documents.id"), nullable=True),
        sa.Column("supersedes_id", sa.Integer(), sa.ForeignKey("hse_assessments.id"), nullable=True),
        sa.Column("task_description", sa.Text(), nullable=False),
        sa.Column("steps", sa.Text(), nullable=False, server_default=""),
        sa.Column("hazards", sa.Text(), nullable=False, server_default=""),
        sa.Column("exposed", sa.Text(), nullable=False, server_default=""),
        sa.Column("existing_controls", sa.Text(), nullable=False, server_default=""),
        sa.Column("initial_rating", sa.String(80), nullable=False, server_default=""),
        sa.Column("additional_controls", sa.Text(), nullable=False, server_default=""),
        sa.Column("residual_rating", sa.String(80), nullable=False, server_default=""),
        sa.Column("control_owners", sa.Text(), nullable=False, server_default=""),
        sa.Column("required_permits", sa.Text(), nullable=False, server_default=""),
        sa.Column("required_competencies", sa.Text(), nullable=False, server_default=""),
        sa.Column("prepared_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("review_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("withdrawal_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_hse_assessment_number"),
        sa.CheckConstraint(
            "status IN ('Draft', 'Pending Review', 'Returned for Correction', 'Approved', 'Rejected', 'Superseded', 'Withdrawn')",
            name="ck_hse_assessment_status",
        ),
    )
    op.create_index("ix_hse_assessments_organization_id", "hse_assessments", ["organization_id"])
    op.create_index("ix_hse_assessments_project_id", "hse_assessments", ["project_id"])
    op.create_index("ix_hse_assessments_package_id", "hse_assessments", ["package_id"])

    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
