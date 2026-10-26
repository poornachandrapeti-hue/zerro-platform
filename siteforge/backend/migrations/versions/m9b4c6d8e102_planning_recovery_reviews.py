"""Recovery reviews and immutable audit events
Revision ID: m9b4c6d8e102
Revises: l8a2c4d6e910
"""
from alembic import op
import sqlalchemy as sa
revision='m9b4c6d8e102'
down_revision='l8a2c4d6e910'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('planning_recovery_reviews',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('scenario_id',sa.Integer(),sa.ForeignKey('planning_recovery_scenarios.id'),nullable=False),
        sa.Column('organization_id',sa.Integer(),nullable=False),sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('department',sa.String(60),nullable=False),sa.Column('decision',sa.String(20),nullable=False),
        sa.Column('comment',sa.Text(),nullable=False),sa.Column('actor_id',sa.Integer(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_recovery_review_scenario','planning_recovery_reviews',['scenario_id'])
    op.create_table('planning_recovery_events',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('scenario_id',sa.Integer(),sa.ForeignKey('planning_recovery_scenarios.id'),nullable=False),
        sa.Column('organization_id',sa.Integer(),nullable=False),sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('previous_status',sa.String(30)),sa.Column('next_status',sa.String(30),nullable=False),
        sa.Column('action',sa.String(40),nullable=False),sa.Column('comment',sa.Text(),nullable=False),
        sa.Column('actor_id',sa.Integer(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_recovery_event_scenario','planning_recovery_events',['scenario_id'])

def downgrade():
    op.drop_index('ix_recovery_event_scenario',table_name='planning_recovery_events')
    op.drop_table('planning_recovery_events')
    op.drop_index('ix_recovery_review_scenario',table_name='planning_recovery_reviews')
    op.drop_table('planning_recovery_reviews')
