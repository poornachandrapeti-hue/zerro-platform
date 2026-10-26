"""Schedule publication snapshots and approval metadata."""
from alembic import op
import sqlalchemy as sa
revision='i3d5e7f9a021'
down_revision='h2c8d4e9f013'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('planning_publications',
       sa.Column('id',sa.Integer,primary_key=True),
       sa.Column('organization_id',sa.Integer,nullable=False),
       sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
       sa.Column('schedule_id',sa.Integer,sa.ForeignKey('planning_schedules.id'),nullable=False),
       sa.Column('revision',sa.String(80),nullable=False),
       sa.Column('status',sa.String(30),nullable=False),
       sa.Column('reason',sa.Text,nullable=False),
       sa.Column('snapshot',sa.JSON,nullable=False),
       sa.Column('submitted_by',sa.Integer,nullable=False),
       sa.Column('submitted_at',sa.DateTime(timezone=True),nullable=False),
       sa.Column('reviewed_by',sa.Integer),
       sa.Column('reviewed_at',sa.DateTime(timezone=True)),
       sa.Column('decision_note',sa.Text),
       sa.Column('is_current',sa.Boolean,nullable=False,server_default=sa.false()),
       sa.UniqueConstraint('schedule_id','revision',name='uq_planning_pub_revision'))
    op.create_index('ix_planning_publications_project_id','planning_publications',['project_id'])
    op.create_index('ix_planning_publications_schedule_id','planning_publications',['schedule_id'])
    op.create_index('ix_planning_publications_organization_id','planning_publications',['organization_id'])

def downgrade():
    op.drop_table('planning_publications')
