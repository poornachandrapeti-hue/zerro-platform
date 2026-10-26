"""Historical approved-baseline verified progress observations."""
from alembic import op
import sqlalchemy as sa
revision='p6a1c3e5f720'
down_revision='p4c6e8a10b32'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('progress_observations',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,nullable=False),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('publication_id',sa.Integer,sa.ForeignKey('planning_publications.id'),nullable=False),
        sa.Column('data_date',sa.Date,nullable=False),
        sa.Column('captured_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('captured_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('verified_percent',sa.Numeric(7,3),nullable=False),
        sa.Column('activity_snapshot',sa.JSON,nullable=False),
        sa.UniqueConstraint('project_id','publication_id','data_date',name='uq_progress_observation_day'))
    op.create_index('ix_progress_observations_org_project','progress_observations',['organization_id','project_id'])

def downgrade():
    op.drop_index('ix_progress_observations_org_project',table_name='progress_observations')
    op.drop_table('progress_observations')
