"""Durable planning alerts and append-only action history."""
from alembic import op
import sqlalchemy as sa
revision='n1c5d7e9f203'
down_revision='m9b4c6d8e102'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('planning_alerts',
        sa.Column('id',sa.Integer(),primary_key=True),sa.Column('organization_id',sa.Integer(),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('dedupe_key',sa.String(180),nullable=False),sa.Column('trigger_type',sa.String(50),nullable=False),
        sa.Column('source_type',sa.String(50),nullable=False),sa.Column('source_id',sa.Integer(),nullable=False),
        sa.Column('title',sa.String(250),nullable=False),sa.Column('description',sa.Text(),nullable=False),
        sa.Column('severity',sa.String(12),nullable=False),sa.Column('owner_id',sa.Integer()),
        sa.Column('status',sa.String(20),nullable=False),sa.Column('first_detected_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('last_detected_at',sa.DateTime(timezone=True),nullable=False),sa.Column('acknowledged_by',sa.Integer()),
        sa.Column('acknowledged_at',sa.DateTime(timezone=True)),sa.Column('resolved_by',sa.Integer()),
        sa.Column('resolved_at',sa.DateTime(timezone=True)),sa.Column('resolution_note',sa.Text(),nullable=False),
        sa.UniqueConstraint('project_id','dedupe_key',name='uq_planning_alert_dedupe'))
    op.create_index('ix_planning_alert_org_project','planning_alerts',['organization_id','project_id'])
    op.create_table('planning_alert_events',
        sa.Column('id',sa.Integer(),primary_key=True),sa.Column('alert_id',sa.Integer(),sa.ForeignKey('planning_alerts.id'),nullable=False),
        sa.Column('organization_id',sa.Integer(),nullable=False),sa.Column('project_id',sa.Integer(),nullable=False),
        sa.Column('actor_id',sa.Integer(),nullable=False),sa.Column('action',sa.String(30),nullable=False),
        sa.Column('note',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_planning_alert_event_alert','planning_alert_events',['alert_id'])

def downgrade():
    op.drop_index('ix_planning_alert_event_alert',table_name='planning_alert_events')
    op.drop_table('planning_alert_events')
    op.drop_index('ix_planning_alert_org_project',table_name='planning_alerts')
    op.drop_table('planning_alerts')
