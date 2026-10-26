"""Vendor return custody, supplier evidence and replacement references (no stock posting)."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase6_vendor_returns'
down_revision = 'stores_phase6_custody_companies'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('stores_vendor_returns',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('reference', sa.String(120), nullable=False),
        sa.Column('vendor_id', sa.Integer(), sa.ForeignKey('procurement_vendors.id'), nullable=False),
        sa.Column('purchase_order_id', sa.Integer(), sa.ForeignKey('purchase_orders.id'), nullable=False),
        sa.Column('item_id', sa.Integer(), sa.ForeignKey('procurement_items.id'), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), sa.ForeignKey('procurement_warehouses.id'), nullable=False),
        sa.Column('quantity', sa.Numeric(14,3), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(40), nullable=False, server_default='Requested'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('approved_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('dispatched_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('vendor_ack_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('replacement_recorded_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('approval_evidence', sa.Text(), nullable=False, server_default=''),
        sa.Column('dispatch_evidence', sa.Text(), nullable=False, server_default=''),
        sa.Column('vendor_ack_evidence', sa.Text(), nullable=False, server_default=''),
        sa.Column('replacement_reference', sa.String(120), nullable=False, server_default=''),
        sa.Column('replacement_evidence', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('project_id', 'reference', name='uq_stores_vendor_return_project_ref'))
    op.create_index('ix_stores_vendor_returns_organization_id', 'stores_vendor_returns', ['organization_id'])
    op.create_index('ix_stores_vendor_returns_project_id', 'stores_vendor_returns', ['project_id'])

def downgrade():
    op.drop_index('ix_stores_vendor_returns_project_id', 'stores_vendor_returns')
    op.drop_index('ix_stores_vendor_returns_organization_id', 'stores_vendor_returns')
    op.drop_table('stores_vendor_returns')
