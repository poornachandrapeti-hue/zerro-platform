"""Trace stock returns to transfer-derived destination lots."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase6_transfer_return_allocation'
down_revision = 'stores_phase6_transfer_issue_allocation'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('stores_transfer_return_allocations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('stock_posting_line_id', sa.Integer(), sa.ForeignKey('stock_posting_lines.id'), nullable=False),
        sa.Column('transfer_destination_lot_id', sa.Integer(), sa.ForeignKey('stores_transfer_destination_lots.id'), nullable=False),
        sa.Column('original_issue_line_id', sa.Integer(), sa.ForeignKey('stock_posting_lines.id'), nullable=False),
        sa.Column('quantity', sa.Numeric(14,3), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('stock_posting_line_id', name='uq_transfer_return_posting_line'))
    for suffix, col in [('org','organization_id'), ('project','project_id'), ('lot','transfer_destination_lot_id')]:
        op.create_index('ix_transfer_return_allocation_' + suffix, 'stores_transfer_return_allocations', [col])

def downgrade():
    for suffix in ('lot', 'project', 'org'):
        op.drop_index('ix_transfer_return_allocation_' + suffix, table_name='stores_transfer_return_allocations')
    op.drop_table('stores_transfer_return_allocations')
