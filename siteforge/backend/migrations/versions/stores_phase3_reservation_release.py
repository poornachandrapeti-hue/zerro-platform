"""Audited partial/full reservation release, without physical movement."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase3_reservation_release'
down_revision = 'stores_phase3_lot_reservations'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('stores_lot_reservation_actions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('reservation_id', sa.Integer(), sa.ForeignKey('stores_lot_reservations.id'), nullable=False),
        sa.Column('action_key', sa.String(120), nullable=False),
        sa.Column('quantity', sa.Numeric(14, 3), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('quantity > 0', name='ck_stores_reservation_release_positive'),
        sa.UniqueConstraint('project_id', 'action_key', name='uq_stores_reservation_action_key'))


def downgrade():
    op.drop_table('stores_lot_reservation_actions')
