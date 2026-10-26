"""Link validated returns to the canonical stock posting."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase5_return_stock_posting'
down_revision = 'stores_phase5_return_custody_qa'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('stores_material_returns', sa.Column('stock_posting_id', sa.Integer(), sa.ForeignKey('stock_postings.id'), nullable=True))
    op.create_unique_constraint('uq_stores_return_stock_posting', 'stores_material_returns', ['stock_posting_id'])

def downgrade():
    op.drop_constraint('uq_stores_return_stock_posting', 'stores_material_returns', type_='unique')
    op.drop_column('stores_material_returns', 'stock_posting_id')
