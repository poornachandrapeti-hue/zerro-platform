"""Planning schedule dependencies. Revision ID: h2c8d4e9f013. Revises: g1b7c3d8e902."""
from alembic import op
import sqlalchemy as sa
revision='h2c8d4e9f013'
down_revision='g1b7c3d8e902'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('planning_dependencies',
      sa.Column('id',sa.Integer,primary_key=True),
      sa.Column('organization_id',sa.Integer,nullable=False),
      sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
      sa.Column('schedule_id',sa.Integer,sa.ForeignKey('planning_schedules.id'),nullable=False),
      sa.Column('predecessor_id',sa.Integer,sa.ForeignKey('planning_activities.id'),nullable=False),
      sa.Column('successor_id',sa.Integer,sa.ForeignKey('planning_activities.id'),nullable=False),
      sa.Column('relation',sa.String(2),nullable=False),
      sa.Column('lag_hours',sa.Integer,nullable=False,server_default='0'),
      sa.UniqueConstraint('schedule_id','predecessor_id','successor_id',name='uq_planning_dep_pair'),
      sa.CheckConstraint('predecessor_id <> successor_id',name='ck_planning_dep_no_self'),
      sa.CheckConstraint("relation IN ('FS','SS','FF','SF')",name='ck_planning_dep_relation'),
      sa.CheckConstraint('lag_hours >= 0',name='ck_planning_dep_lag'))
    op.create_index('ix_planning_dependencies_schedule_id','planning_dependencies',['schedule_id'])
    op.create_index('ix_planning_dependencies_project_id','planning_dependencies',['project_id'])

def downgrade():
    op.drop_table('planning_dependencies')
