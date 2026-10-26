"""allow a discipline head to be a requisition reviewer"""

from alembic import op

revision = "c8f3a1d64e20"
down_revision = "b4d9e2c71a06"
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
