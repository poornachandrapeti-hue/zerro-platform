"""Planning workspace foundation. Revision ID: g1b7c3d8e902. Revises: f9a6b2c7d801."""
from alembic import op
import sqlalchemy as sa
revision='g1b7c3d8e902'
down_revision='f9a6b2c7d801'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('planning_wbs',sa.Column('id',sa.Integer,primary_key=True),sa.Column('organization_id',sa.Integer,nullable=False),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),sa.Column('code',sa.String(80),nullable=False),sa.Column('name',sa.String(200),nullable=False),sa.Column('parent_id',sa.Integer,sa.ForeignKey('planning_wbs.id')),sa.Column('description',sa.Text,nullable=False),sa.Column('company_id',sa.Integer),sa.Column('discipline_id',sa.Integer),sa.Column('location_id',sa.Integer),sa.Column('owner_id',sa.Integer),sa.Column('active',sa.Boolean,nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('project_id','code',name='uq_planning_wbs_project_code'))
    op.create_table('planning_calendars',sa.Column('id',sa.Integer,primary_key=True),sa.Column('organization_id',sa.Integer,nullable=False),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),sa.Column('code',sa.String(80),nullable=False),sa.Column('name',sa.String(200),nullable=False),sa.Column('timezone',sa.String(100),nullable=False),sa.Column('working_days',sa.JSON,nullable=False),sa.Column('shift_start',sa.String(5),nullable=False),sa.Column('shift_end',sa.String(5),nullable=False),sa.Column('holidays',sa.JSON,nullable=False),sa.Column('version',sa.Integer,nullable=False),sa.UniqueConstraint('project_id','code',name='uq_planning_calendar_project_code'))
    op.create_table('planning_schedules',sa.Column('id',sa.Integer,primary_key=True),sa.Column('organization_id',sa.Integer,nullable=False),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),sa.Column('name',sa.String(200),nullable=False),sa.Column('kind',sa.String(30),nullable=False),sa.Column('version',sa.String(50),nullable=False),sa.Column('data_date',sa.Date,nullable=False),sa.Column('calendar_id',sa.Integer,sa.ForeignKey('planning_calendars.id'),nullable=False),sa.Column('owner_id',sa.Integer,nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('description',sa.Text,nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('project_id','name','version',name='uq_planning_schedule_version'))
    op.create_table('planning_activities',sa.Column('id',sa.Integer,primary_key=True),sa.Column('organization_id',sa.Integer,nullable=False),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),sa.Column('schedule_id',sa.Integer,sa.ForeignKey('planning_schedules.id'),nullable=False),sa.Column('wbs_id',sa.Integer,sa.ForeignKey('planning_wbs.id'),nullable=False),sa.Column('calendar_id',sa.Integer,sa.ForeignKey('planning_calendars.id'),nullable=False),sa.Column('code',sa.String(80),nullable=False),sa.Column('name',sa.String(240),nullable=False),sa.Column('activity_type',sa.String(20),nullable=False),sa.Column('company_id',sa.Integer,nullable=False),sa.Column('discipline_id',sa.Integer),sa.Column('owner_id',sa.Integer),sa.Column('location_id',sa.Integer),sa.Column('duration_hours',sa.Integer),sa.Column('planned_start',sa.Date),sa.Column('planned_finish',sa.Date),sa.Column('progress_method',sa.String(30)),sa.Column('source_type',sa.String(60)),sa.Column('source_id',sa.String(100)),sa.Column('remarks',sa.Text,nullable=False),sa.UniqueConstraint('schedule_id','code',name='uq_planning_activity_schedule_code'))
    for table in ('planning_wbs','planning_calendars','planning_schedules','planning_activities'):
        op.create_index('ix_'+table+'_project_id',table,['project_id'])
        op.create_index('ix_'+table+'_organization_id',table,['organization_id'])
    op.create_index('ix_planning_activities_schedule_id','planning_activities',['schedule_id'])

def downgrade():
    for table in ('planning_activities','planning_schedules','planning_calendars','planning_wbs'):
        op.drop_table(table)
