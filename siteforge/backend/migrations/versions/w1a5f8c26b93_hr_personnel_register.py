"""HR personnel register and workforce lists. downgrade is pass."""

import sqlalchemy as sa
from alembic import op

revision = "w1a5f8c26b93"
down_revision = "v9h4e7c14a82"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hr_masters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("name_key", sa.String(120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "kind", "name_key", name="uq_hr_master_name"),
        sa.CheckConstraint(
            "kind IN ('Designation', 'Trade', 'Skill grade', 'Training type', 'Document requirement')",
            name="ck_hr_master_kind",
        ),
    )
    op.create_index("ix_hr_masters_organization_id", "hr_masters", ["organization_id"])
    op.create_table(
        "hr_personnel",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("code_key", sa.String(40), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("personnel_type", sa.String(40), nullable=False),
        sa.Column("designation_id", sa.Integer(), sa.ForeignKey("hr_masters.id"), nullable=False),
        sa.Column("trade_id", sa.Integer(), sa.ForeignKey("hr_masters.id"), nullable=False),
        sa.Column("grade_id", sa.Integer(), sa.ForeignKey("hr_masters.id"), nullable=True),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("hr_personnel.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Active"),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("contact_number", sa.String(40), nullable=False, server_default=""),
        sa.Column("emergency_contact", sa.Text(), nullable=False, server_default=""),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("address", sa.Text(), nullable=False, server_default=""),
        sa.Column("identity_reference", sa.String(120), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "code_key", name="uq_hr_personnel_code"),
        sa.UniqueConstraint("user_id", name="uq_hr_personnel_user"),
        sa.CheckConstraint(
            "personnel_type IN ('Employee', 'Contract Worker', 'Temporary Worker', 'Consultant')",
            name="ck_hr_personnel_type",
        ),
        sa.CheckConstraint("status IN ('Active', 'Inactive', 'Separated')", name="ck_hr_personnel_status"),
    )
    op.create_index("ix_hr_personnel_organization_id", "hr_personnel", ["organization_id"])
    op.create_index("ix_hr_personnel_company_id", "hr_personnel", ["company_id"])

    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
