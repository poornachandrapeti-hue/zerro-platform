"""Planning look-ahead records; revision k6f9a1b2c345."""
from alembic import op
import sqlalchemy as sa
revision='k6f9a1b2c345'
down_revision='j5e8c2d4f710'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('planning_lookaheads',sa.Column('id',sa.Integer,primary_key=True),sa.Column('organization_id',sa.Integer,nullable=False),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),sa.Column('code',sa.String(80),nullable=False),sa.Column('schedule_id',sa.Integer,sa.ForeignKey('planning_schedules.id'),nullable=False),sa.Column('horizon',sa.String(12),nullable=False),sa.Column('start_date',sa.Date,nullable=False),sa.Column('end_date',sa.Date,nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('created_by',sa.Integer,nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('project_id','code',name='uq_lookahead_project_code'))
    op.create_index('ix_planning_lookaheads_project_id','planning_lookaheads',['project_id'])
    op.create_table('planning_lookahead_items',sa.Column('id',sa.Integer,primary_key=True),sa.Column('organization_id',sa.Integer,nullable=False),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),sa.Column('lookahead_id',sa.Integer,sa.ForeignKey('planning_lookaheads.id'),nullable=False),sa.Column('activity_id',sa.Integer,sa.ForeignKey('planning_activities.id'),nullable=False),sa.Column('target_date',sa.Date,nullable=False),sa.Column('target_quantity',sa.Integer),sa.Column('target_unit',sa.String(40)),sa.Column('owner_id',sa.Integer,nullable=False),sa.Column('commitment',sa.String(20),nullable=False),sa.Column('readiness',sa.String(20),nullable=False),sa.Column('readiness_notes',sa.Text,nullable=False),sa.Column('blocker',sa.Text,nullable=False),sa.Column('resolution_owner_id',sa.Integer),sa.Column('resolution_due',sa.Date),sa.Column('achieved_quantity',sa.Integer),sa.Column('variance_reason',sa.Text,nullable=False),sa.Column('updated_by',sa.Integer,nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('lookahead_id','activity_id',name='uq_lookahead_activity'))
    op.create_index('ix_planning_lookahead_items_project_id','planning_lookahead_items',['project_id'])
    op.create_index('ix_planning_lookahead_items_lookahead_id','planning_lookahead_items',['lookahead_id'])

def downgrade():
    op.drop_table('planning_lookahead_items')
    op.drop_table('planning_lookaheads')
