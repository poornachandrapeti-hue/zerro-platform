"""Stores discrepancy review evidence; no stock changes."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase5_discrepancy_resolution'
down_revision = 'stores_phase5_material_handover'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('stores_material_handovers', sa.Column('resolution_note', sa.Text(), nullable=False, server_default=''))
    op.add_column('stores_material_handovers', sa.Column('resolved_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('stores_material_handovers', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column('stores_material_handovers', 'resolved_at')
    op.drop_column('stores_material_handovers', 'resolved_by')
    op.drop_column('stores_material_handovers', 'resolution_note')
