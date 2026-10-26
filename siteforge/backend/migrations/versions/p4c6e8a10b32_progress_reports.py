"""Progress publication and audit history."""
from alembic import op
import sqlalchemy as sa
revision='p4c6e8a10b32'
down_revision='f5c392e28a47'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('progress_monitoring_reports',
        sa.Column('id',sa.Integer,primary_key=True),sa.Column('organization_id',sa.Integer,nullable=False),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('report_number',sa.String(80),nullable=False),sa.Column('revision',sa.Integer,nullable=False),
        sa.Column('report_type',sa.String(12),nullable=False),sa.Column('period_start',sa.Date,nullable=False),
        sa.Column('period_end',sa.Date,nullable=False),sa.Column('data_date',sa.Date,nullable=False),
        sa.Column('status',sa.String(24),nullable=False),sa.Column('commentary',sa.Text,nullable=False),
        sa.Column('prepared_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('reviewer_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('approver_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('snapshot',sa.JSON,nullable=True),sa.Column('source_cutoff',sa.DateTime(timezone=True),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('published_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('reason',sa.Text,nullable=False),
        sa.UniqueConstraint('project_id','report_number','revision',name='uq_progress_report_revision'))
    op.create_table('progress_report_events',sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,nullable=False),sa.Column('project_id',sa.Integer,nullable=False),
        sa.Column('report_id',sa.Integer,sa.ForeignKey('progress_monitoring_reports.id'),nullable=False),
        sa.Column('actor_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('event',sa.String(32),nullable=False),sa.Column('note',sa.Text,nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    for table in ('progress_monitoring_reports','progress_report_events'):
        op.create_index('ix_'+table+'_project',table,['organization_id','project_id'])
    op.create_index('ix_progress_report_events_report_id','progress_report_events',['report_id'])

def downgrade():
    op.drop_table('progress_report_events');op.drop_table('progress_monitoring_reports')
