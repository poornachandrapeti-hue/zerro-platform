"""Phase 6 warehouse transfer custody evidence (no inventory posting)."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase6_transfer_custody'
down_revision = 'a5f15015c001'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('stores_transfers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('reference', sa.String(120), nullable=False),
        sa.Column('source_warehouse_id', sa.Integer(), sa.ForeignKey('procurement_warehouses.id'), nullable=False),
        sa.Column('destination_warehouse_id', sa.Integer(), sa.ForeignKey('procurement_warehouses.id'), nullable=False),
        sa.Column('item_id', sa.Integer(), sa.ForeignKey('procurement_items.id'), nullable=False),
        sa.Column('quantity', sa.Numeric(14,3), nullable=False),
        sa.Column('purpose', sa.Text(), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('approved_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('dispatched_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('received_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('dispatched_quantity', sa.Numeric(14,3)),
        sa.Column('received_quantity', sa.Numeric(14,3)),
        sa.Column('damaged_quantity', sa.Numeric(14,3)),
        sa.Column('approval_evidence', sa.Text(), nullable=False, server_default=''),
        sa.Column('dispatch_evidence', sa.Text(), nullable=False, server_default=''),
        sa.Column('receipt_evidence', sa.Text(), nullable=False, server_default=''),
        sa.Column('discrepancy_note', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('project_id','reference',name='uq_stores_transfer_project_reference'))
    op.create_index('ix_stores_transfers_organization_id','stores_transfers',['organization_id'])
    op.create_index('ix_stores_transfers_project_id','stores_transfers',['project_id'])

def downgrade():
    op.drop_index('ix_stores_transfers_project_id',table_name='stores_transfers')
    op.drop_index('ix_stores_transfers_organization_id',table_name='stores_transfers')
    op.drop_table('stores_transfers')
