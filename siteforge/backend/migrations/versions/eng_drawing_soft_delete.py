"""Soft deletion of draft drawings and the explicit drawing deletion role.
Revision ID: eng_drawing_soft_delete
Revises: progress_p3c1fe_qa_files
"""
from alembic import op
import sqlalchemy as sa
revision = 'eng_drawing_soft_delete'
down_revision = 'progress_p3c1fe_qa_files'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('drawings', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('drawings', sa.Column('deleted_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('drawings', sa.Column('deletion_reason', sa.Text(), nullable=False, server_default=''))
    from sqlalchemy.orm import Session
    from app.domains.identity_projects.models import Role
    from app.domains.identity_projects.seed import DRAWING_DELETION_ROLE, default_permissions
    session = Session(bind=op.get_bind())
    if not session.query(Role).filter_by(name=DRAWING_DELETION_ROLE).first():
        session.add(Role(name=DRAWING_DELETION_ROLE, permissions=default_permissions(DRAWING_DELETION_ROLE)))
    session.flush()

def downgrade():
    # The role is retained on rollback: memberships may reference it.
    op.drop_column('drawings', 'deletion_reason')
    op.drop_column('drawings', 'deleted_by')
    op.drop_column('drawings', 'deleted_at')
