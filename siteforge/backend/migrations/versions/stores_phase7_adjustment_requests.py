"""Phase 7 count-linked adjustment reviews. No stock ledger mutation."""
from alembic import op
import sqlalchemy as sa
revision='stores_phase7_adjustment_requests'
down_revision='stores_phase7_cycle_counts'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('stores_stock_adjustment_requests',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('count_id',sa.Integer(),sa.ForeignKey('stores_cycle_counts.id'),nullable=False),
        sa.Column('reference',sa.String(120),nullable=False),
        sa.Column('reason',sa.Text(),nullable=False),
        sa.Column('evidence',sa.Text(),nullable=False),
        sa.Column('status',sa.String(32),nullable=False,server_default='PendingReconciliation'),
        sa.Column('version',sa.Integer(),nullable=False,server_default='1'),
        sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('reviewed_by',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('review_evidence',sa.Text(),nullable=False,server_default=''),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('project_id','reference',name='uq_stores_adjustment_reference'))
    op.create_index('ix_stores_adjustment_scope','stores_stock_adjustment_requests',['organization_id','project_id'])
    op.create_index('ix_stores_adjustment_count','stores_stock_adjustment_requests',['count_id'])

def downgrade():
    op.drop_index('ix_stores_adjustment_count',table_name='stores_stock_adjustment_requests')
    op.drop_index('ix_stores_adjustment_scope',table_name='stores_stock_adjustment_requests')
    op.drop_table('stores_stock_adjustment_requests')
