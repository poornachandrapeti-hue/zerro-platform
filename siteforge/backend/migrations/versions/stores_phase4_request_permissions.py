"""Grant distinct Stores request permissions to existing roles."""
from alembic import op
revision = 'stores_phase4_request_permissions'
down_revision = 'stores_phase4_partner_issue_requests'
branch_labels = None
depends_on = None

def upgrade():
    from sqlalchemy.orm import Session
    from app.domains.identity_projects.seed import grant_role_permissions
    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()

def downgrade():
    # Grants are intentionally not revoked on rollback: manual role edits may exist.
    pass
