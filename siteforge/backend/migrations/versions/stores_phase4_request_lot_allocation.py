"""Link lot reservations to approved Stores issue requests (canonical procurement demand)."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase4_request_lot_allocation'
down_revision = 'stores_phase4_shared_requirement_link'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('stores_lot_reservations', sa.Column('material_request_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_stores_lot_reservation_issue_request', 'stores_lot_reservations', 'stores_material_requests', ['material_request_id'], ['id'])
    op.create_index('ix_stores_lot_reservations_material_request_id', 'stores_lot_reservations', ['material_request_id'])

def downgrade():
    op.drop_index('ix_stores_lot_reservations_material_request_id', table_name='stores_lot_reservations')
    op.drop_constraint('fk_stores_lot_reservation_issue_request', 'stores_lot_reservations', type_='foreignkey')
    op.drop_column('stores_lot_reservations', 'material_request_id')
