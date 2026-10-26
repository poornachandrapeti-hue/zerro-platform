"""Phase 6 transfer discrepancy follow-up, custody only."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase6_transfer_discrepancy'
down_revision = 'stores_phase6_transfer_custody'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('stores_transfers', sa.Column('discrepancy_status', sa.String(32), nullable=False, server_default='Not Required'))
    op.add_column('stores_transfers', sa.Column('discrepancy_resolution', sa.Text(), nullable=False, server_default=''))
    op.add_column('stores_transfers', sa.Column('discrepancy_resolved_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.execute("UPDATE stores_transfers SET discrepancy_status = 'Open' WHERE status = 'Discrepancy'")

def downgrade():
    op.drop_column('stores_transfers', 'discrepancy_resolved_by')
    op.drop_column('stores_transfers', 'discrepancy_resolution')
    op.drop_column('stores_transfers', 'discrepancy_status')
