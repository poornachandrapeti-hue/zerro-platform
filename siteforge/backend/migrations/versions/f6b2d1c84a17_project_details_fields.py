"""project commercial fields, discipline scope, and document titles"""

import sqlalchemy as sa
from alembic import op

revision = "f6b2d1c84a17"
down_revision = "e5c2a9b81d04"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("modified_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_projects_modified_by_users", "projects", "users", ["modified_by"], ["id"]
    )
    op.add_column(
        "projects",
        sa.Column("contract_number", sa.String(length=80), nullable=False, server_default=""),
    )
    op.add_column("projects", sa.Column("contract_date", sa.Date(), nullable=True))
    op.add_column("projects", sa.Column("contract_value", sa.Numeric(14, 2), nullable=True))
    op.add_column(
        "projects",
        sa.Column("currency", sa.String(length=8), nullable=False, server_default=""),
    )
    op.add_column(
        "project_disciplines",
        sa.Column("scope_description", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "project_disciplines",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "project_files",
        sa.Column("title", sa.String(length=200), nullable=False, server_default=""),
    )
    op.add_column(
        "project_files",
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )
    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    op.drop_column("project_files", "description")
    op.drop_column("project_files", "title")
    op.drop_column("project_disciplines", "active")
    op.drop_column("project_disciplines", "scope_description")
    op.drop_column("projects", "currency")
    op.drop_column("projects", "contract_value")
    op.drop_column("projects", "contract_date")
    op.drop_column("projects", "contract_number")
    op.drop_constraint("fk_projects_modified_by_users", "projects", type_="foreignkey")
    op.drop_column("projects", "modified_by")
