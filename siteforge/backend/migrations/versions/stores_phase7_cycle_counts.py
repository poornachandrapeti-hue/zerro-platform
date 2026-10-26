"""Phase 7 cycle count observation and independent review; no inventory posting."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase7_cycle_counts'
down_revision = 'stores_phase7_preservation'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('stores_cycle_counts',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('warehouse_id',sa.Integer(),sa.ForeignKey('procurement_warehouses.id'),nullable=False),
        sa.Column('reference',sa.String(120),nullable=False),
        sa.Column('scheduled_date',sa.Date(),nullable=False),
        sa.Column('status',sa.String(24),nullable=False,server_default='Draft'),
        sa.Column('version',sa.Integer(),nullable=False,server_default='1'),
        sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('submitted_by',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('verified_by',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('review_evidence',sa.Text(),nullable=False,server_default=''),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('project_id','reference',name='uq_stores_cycle_count_ref'))
    op.create_index('ix_stores_cycle_counts_org_project','stores_cycle_counts',['organization_id','project_id'])
    op.create_table('stores_cycle_count_lines',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('count_id',sa.Integer(),sa.ForeignKey('stores_cycle_counts.id'),nullable=False),
        sa.Column('receipt_lot_id',sa.Integer(),sa.ForeignKey('stores_receipt_lots.id'),nullable=False),
        sa.Column('observed_quantity',sa.Numeric(14,3),nullable=False),
        sa.Column('recorded_lot_quantity',sa.Numeric(14,3),nullable=False),
        sa.Column('evidence',sa.Text(),nullable=False),
        sa.Column('counted_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('counted_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('count_id','receipt_lot_id',name='uq_stores_cycle_count_lot'),
        sa.CheckConstraint('observed_quantity >= 0',name='ck_stores_count_observed_nonnegative'))

def downgrade():
    op.drop_table('stores_cycle_count_lines')
    op.drop_index('ix_stores_cycle_counts_org_project',table_name='stores_cycle_counts')
    op.drop_table('stores_cycle_counts')
