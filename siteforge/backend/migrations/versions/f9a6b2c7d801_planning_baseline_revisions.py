"""Create native SiteForge planning baseline revision register.

Revision ID: f9a6b2c7d801
Revises: e3c9e5a74b12
"""
from alembic import op
import sqlalchemy as sa

revision = 'f9a6b2c7d801'
down_revision = 'e3c9e5a74b12'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('planning_baseline_revisions',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),nullable=False),
        sa.Column('project_id',sa.Integer(),nullable=False),
        sa.Column('revision',sa.String(80),nullable=False),
        sa.Column('status',sa.String(20),nullable=False),
        sa.Column('document',sa.JSON(),nullable=False),
        sa.Column('created_by',sa.Integer(),nullable=False),
        sa.Column('approved_by',sa.Integer()),
        sa.Column('approved_at',sa.DateTime(timezone=True)),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('project_id','revision',name='uq_planning_baseline_project_revision'))
    op.create_index('ix_planning_baseline_revisions_organization_id','planning_baseline_revisions',['organization_id'])
    op.create_index('ix_planning_baseline_revisions_project_id','planning_baseline_revisions',['project_id'])

def downgrade():
    op.drop_index('ix_planning_baseline_revisions_project_id',table_name='planning_baseline_revisions')
    op.drop_index('ix_planning_baseline_revisions_organization_id',table_name='planning_baseline_revisions')
    op.drop_table('planning_baseline_revisions')
