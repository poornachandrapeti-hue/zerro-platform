"""Single reservation table supports GRN or transfer provenance; transfer entries remain non-posting."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase6_unified_reservation_source'
down_revision = 'stores_phase6_transfer_destination_lots'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('stores_lot_reservations', 'receipt_lot_id', existing_type=sa.Integer(), nullable=True)
    op.add_column('stores_lot_reservations', sa.Column('transfer_destination_lot_id', sa.Integer(), sa.ForeignKey('stores_transfer_destination_lots.id'), nullable=True))
    op.create_index('ix_stores_lot_reservations_transfer_destination_lot_id', 'stores_lot_reservations', ['transfer_destination_lot_id'])
    op.create_check_constraint('ck_stores_reservation_exactly_one_lot', 'stores_lot_reservations', '(receipt_lot_id IS NOT NULL AND transfer_destination_lot_id IS NULL) OR (receipt_lot_id IS NULL AND transfer_destination_lot_id IS NOT NULL)')


def downgrade():
    op.drop_constraint('ck_stores_reservation_exactly_one_lot', 'stores_lot_reservations', type_='check')
    op.drop_index('ix_stores_lot_reservations_transfer_destination_lot_id', table_name='stores_lot_reservations')
    op.drop_column('stores_lot_reservations', 'transfer_destination_lot_id')
    op.alter_column('stores_lot_reservations', 'receipt_lot_id', existing_type=sa.Integer(), nullable=False)
