"""project contacts, kept separate from approvers"""

import sqlalchemy as sa
from alembic import op

revision = "b7e3c9a15d40"
down_revision = "d2f6b8c41a09"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "project_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("function", sa.String(40), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("phone", sa.String(40), nullable=False, server_default=""),
        sa.Column("email", sa.String(254), nullable=False, server_default=""),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "function IN ('Client', 'PMC', 'Project manager', 'Discipline', "
            "'Procurement', 'Stores', 'Site', 'Safety', 'Other')",
            name="ck_project_contact_function",
        ),
    )
    op.create_index("ix_project_contacts_organization_id", "project_contacts", ["organization_id"])
    op.create_index("ix_project_contacts_project_id", "project_contacts", ["project_id"])

    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
