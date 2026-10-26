"""Durable transfer lot provenance planning; no physical ledger changes."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase6_transfer_lot_lineage'
down_revision = 'stores_phase6_vendor_returns'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('stores_transfer_lot_lineage',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('transfer_id', sa.Integer(), sa.ForeignKey('stores_transfers.id'), nullable=False),
        sa.Column('source_receipt_lot_id', sa.Integer(), sa.ForeignKey('stores_receipt_lots.id'), nullable=False),
        sa.Column('destination_receipt_lot_id', sa.Integer(), sa.ForeignKey('stores_receipt_lots.id')),
        sa.Column('source_posting_id', sa.Integer(), sa.ForeignKey('stock_postings.id')),
        sa.Column('destination_posting_id', sa.Integer(), sa.ForeignKey('stock_postings.id')),
        sa.Column('quantity', sa.Numeric(14,3), nullable=False),
        sa.Column('status', sa.String(24), nullable=False, server_default='Planned'),
        sa.Column('evidence', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('transfer_id', name='uq_stores_transfer_lineage_transfer'))
    for column in ('organization_id', 'project_id', 'transfer_id'):
        op.create_index('ix_stores_transfer_lot_lineage_' + column, 'stores_transfer_lot_lineage', [column])


def downgrade():
    op.drop_table('stores_transfer_lot_lineage')
