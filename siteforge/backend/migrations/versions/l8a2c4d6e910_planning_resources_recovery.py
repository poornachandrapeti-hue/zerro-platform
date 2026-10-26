"""planning resource demand and recovery scenarios
Revision ID: l8a2c4d6e910
Revises: k6f9a1b2c345
"""
from alembic import op
import sqlalchemy as sa
revision='l8a2c4d6e910'
down_revision='k6f9a1b2c345'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('planning_resource_demands',
        sa.Column('id',sa.Integer(),primary_key=True),sa.Column('organization_id',sa.Integer(),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('schedule_id',sa.Integer(),sa.ForeignKey('planning_schedules.id'),nullable=False),
        sa.Column('activity_id',sa.Integer(),sa.ForeignKey('planning_activities.id'),nullable=False),
        sa.Column('period_start',sa.Date(),nullable=False),sa.Column('period_end',sa.Date(),nullable=False),
        sa.Column('resource_type',sa.String(20),nullable=False),sa.Column('resource_name',sa.String(160),nullable=False),
        sa.Column('company_id',sa.Integer()),sa.Column('demand_quantity',sa.Integer(),nullable=False),
        sa.Column('demand_unit',sa.String(20),nullable=False),sa.Column('confirmed_capacity',sa.Integer()),
        sa.Column('capacity_source',sa.String(200)),sa.Column('notes',sa.Text(),nullable=False),
        sa.Column('created_by',sa.Integer(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_plan_demand_project','planning_resource_demands',['project_id'])
    op.create_table('planning_recovery_scenarios',
        sa.Column('id',sa.Integer(),primary_key=True),sa.Column('organization_id',sa.Integer(),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('schedule_id',sa.Integer(),sa.ForeignKey('planning_schedules.id'),nullable=False),
        sa.Column('code',sa.String(80),nullable=False),sa.Column('title',sa.String(200),nullable=False),
        sa.Column('reason',sa.Text(),nullable=False),sa.Column('proposed_changes',sa.Text(),nullable=False),
        sa.Column('schedule_impact_days',sa.Integer()),sa.Column('resource_impact',sa.Text(),nullable=False),
        sa.Column('cost_impact_reference',sa.String(200)),sa.Column('required_reviews',sa.JSON(),nullable=False),
        sa.Column('status',sa.String(20),nullable=False),sa.Column('created_by',sa.Integer(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('project_id','code',name='uq_planning_recovery_code'))
    op.create_index('ix_plan_recovery_project','planning_recovery_scenarios',['project_id'])

def downgrade():
    op.drop_index('ix_plan_recovery_project',table_name='planning_recovery_scenarios')
    op.drop_table('planning_recovery_scenarios')
    op.drop_index('ix_plan_demand_project',table_name='planning_resource_demands')
    op.drop_table('planning_resource_demands')
