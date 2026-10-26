"""Apply Financials and Contracts role grants to existing roles; Revision ID: cm0122; Revises: cm0121."""
from alembic import op
revision = 'cm0122'
down_revision = 'cm0121'
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
