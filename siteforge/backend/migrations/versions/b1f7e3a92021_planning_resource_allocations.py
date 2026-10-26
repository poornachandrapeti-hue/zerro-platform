"""Planning allocation proposals, separated from authoritative workforce/equipment assignments.
Revision ID: b1f7e3a92021
Revises: p3f13a8b2140
"""
from alembic import op
import sqlalchemy as sa
revision='b1f7e3a92021'
down_revision='p3f13a8b2140'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('planning_resource_allocations',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,nullable=False),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('schedule_id',sa.Integer,sa.ForeignKey('planning_schedules.id'),nullable=False),
        sa.Column('activity_id',sa.Integer,sa.ForeignKey('planning_activities.id'),nullable=False),
        sa.Column('resource_type',sa.String(20),nullable=False),
        sa.Column('resource_ref',sa.String(120),nullable=False),
        sa.Column('company_id',sa.Integer),
        sa.Column('starts_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('ends_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('status',sa.String(20),nullable=False),
        sa.Column('notes',sa.Text,nullable=False),
        sa.Column('created_by',sa.Integer,nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint('ends_at > starts_at',name='ck_planning_resource_allocation_dates'),
        sa.CheckConstraint("resource_type IN ('Workforce','Equipment')",name='ck_planning_resource_type'))
    op.create_index('ix_planning_alloc_resource','planning_resource_allocations',['organization_id','project_id','resource_type','resource_ref'])
    op.create_index('ix_planning_alloc_schedule','planning_resource_allocations',['schedule_id'])

def downgrade():
    op.drop_index('ix_planning_alloc_schedule',table_name='planning_resource_allocations')
    op.drop_index('ix_planning_alloc_resource',table_name='planning_resource_allocations')
    op.drop_table('planning_resource_allocations')
