"""Link outgoing stock posting lines to transfer-derived lots."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase6_transfer_issue_allocation'
down_revision = 'stores_phase6_unified_reservation_source'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('stores_transfer_issue_allocations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('stock_posting_line_id', sa.Integer(), sa.ForeignKey('stock_posting_lines.id'), nullable=False),
        sa.Column('transfer_destination_lot_id', sa.Integer(), sa.ForeignKey('stores_transfer_destination_lots.id'), nullable=False),
        sa.Column('reservation_id', sa.Integer(), sa.ForeignKey('stores_lot_reservations.id'), nullable=False),
        sa.Column('quantity', sa.Numeric(14,3), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('stock_posting_line_id', name='uq_transfer_issue_posting_line'))
    op.create_index('ix_transfer_issue_allocation_org', 'stores_transfer_issue_allocations', ['organization_id'])
    op.create_index('ix_transfer_issue_allocation_project', 'stores_transfer_issue_allocations', ['project_id'])
    op.create_index('ix_transfer_issue_allocation_lot', 'stores_transfer_issue_allocations', ['transfer_destination_lot_id'])

def downgrade():
    op.drop_index('ix_transfer_issue_allocation_lot', table_name='stores_transfer_issue_allocations')
    op.drop_index('ix_transfer_issue_allocation_project', table_name='stores_transfer_issue_allocations')
    op.drop_index('ix_transfer_issue_allocation_org', table_name='stores_transfer_issue_allocations')
    op.drop_table('stores_transfer_issue_allocations')
