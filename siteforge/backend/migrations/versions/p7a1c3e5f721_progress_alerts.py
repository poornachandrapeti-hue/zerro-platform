"""Project progress alert thresholds and persistent alert register."""
from alembic import op
import sqlalchemy as sa
revision='p7a1c3e5f721'
down_revision='p6a1c3e5f720'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('progress_alert_policies',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,nullable=False),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False,unique=True),
        sa.Column('warning_pp',sa.Numeric(6,2),nullable=False),
        sa.Column('critical_pp',sa.Numeric(6,2),nullable=False),
        sa.Column('updated_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('progress_alert_events',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,nullable=False),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('fingerprint',sa.String(160),nullable=False),
        sa.Column('kind',sa.String(60),nullable=False),
        sa.Column('severity',sa.String(20),nullable=False),
        sa.Column('message',sa.Text,nullable=False),
        sa.Column('state',sa.String(24),nullable=False),
        sa.Column('first_seen',sa.DateTime(timezone=True),nullable=False),
        sa.Column('last_seen',sa.DateTime(timezone=True),nullable=False),
        sa.Column('acknowledged_by',sa.Integer,sa.ForeignKey('users.id')),
        sa.Column('acknowledged_at',sa.DateTime(timezone=True)),
        sa.Column('escalated_by',sa.Integer,sa.ForeignKey('users.id')),
        sa.Column('escalated_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('project_id','fingerprint',name='uq_progress_alert_fingerprint'))
    op.create_index('ix_progress_alert_event_scope','progress_alert_events',['organization_id','project_id'])

def downgrade():
    op.drop_index('ix_progress_alert_event_scope',table_name='progress_alert_events')
    op.drop_table('progress_alert_events')
    op.drop_table('progress_alert_policies')
