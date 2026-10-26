"""Versioned Engineering and Procurement milestone policies."""
from alembic import op
import sqlalchemy as sa
revision='p9a1c4e7f723'
down_revision='p8b1c4e6f722'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('progress_milestone_policies',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,nullable=False),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('stage',sa.String(30),nullable=False),
        sa.Column('version',sa.Integer,nullable=False),
        sa.Column('status',sa.String(20),nullable=False),
        sa.Column('milestone_weights',sa.JSON,nullable=False),
        sa.Column('planning_publication_id',sa.Integer,sa.ForeignKey('planning_publications.id'),nullable=False),
        sa.Column('approval_reference',sa.String(160)),
        sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('approved_by',sa.Integer,sa.ForeignKey('users.id')),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('approved_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('project_id','stage','version',name='uq_progress_milestone_policy_version'))
    op.create_index('ix_progress_milestone_policies_project_id','progress_milestone_policies',['project_id'])
def downgrade():
    op.drop_index('ix_progress_milestone_policies_project_id',table_name='progress_milestone_policies')
    op.drop_table('progress_milestone_policies')
