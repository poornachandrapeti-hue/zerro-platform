"""Return bin custody assignment; never a separate bin stock ledger."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase5_return_bin_placement'
down_revision = 'stores_phase5_return_stock_posting'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('stores_material_returns', sa.Column('return_location_id', sa.Integer(), sa.ForeignKey('stores_locations.id'), nullable=True))
    op.add_column('stores_material_returns', sa.Column('placement_evidence', sa.Text(), nullable=False, server_default=''))
    op.add_column('stores_material_returns', sa.Column('placement_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))

def downgrade():
    op.drop_column('stores_material_returns', 'placement_by')
    op.drop_column('stores_material_returns', 'placement_evidence')
    op.drop_column('stores_material_returns', 'return_location_id')
