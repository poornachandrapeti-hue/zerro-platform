"""Destination transfer provenance (not a stock ledger or QA release)."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase6_transfer_destination_lots'
down_revision = 'stores_phase6_transfer_lot_lineage'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('stores_transfer_destination_lots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('source_project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('destination_project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('transfer_id', sa.Integer(), sa.ForeignKey('stores_transfers.id'), nullable=False),
        sa.Column('lineage_id', sa.Integer(), sa.ForeignKey('stores_transfer_lot_lineage.id'), nullable=False),
        sa.Column('source_receipt_lot_id', sa.Integer(), sa.ForeignKey('stores_receipt_lots.id'), nullable=False),
        sa.Column('destination_warehouse_id', sa.Integer(), sa.ForeignKey('procurement_warehouses.id'), nullable=False),
        sa.Column('item_id', sa.Integer(), sa.ForeignKey('procurement_items.id'), nullable=False),
        sa.Column('lot_code', sa.String(100), nullable=False),
        sa.Column('quantity', sa.Numeric(14, 3), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('transfer_id', name='uq_stores_destination_lot_transfer'),
        sa.UniqueConstraint('destination_warehouse_id', 'lot_code', name='uq_stores_destination_lot_code'))
    for col in ('organization_id', 'transfer_id'):
        op.create_index('ix_stores_transfer_destination_lots_' + col, 'stores_transfer_destination_lots', [col])


def downgrade():
    op.drop_table('stores_transfer_destination_lots')
