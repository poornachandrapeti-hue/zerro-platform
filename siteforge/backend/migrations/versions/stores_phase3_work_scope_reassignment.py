"""Work-package/WBS-scoped lot reservation with reassignment audit."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase3_work_scope_reassignment'
down_revision = 'stores_phase3_reservation_release'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('stores_lot_reservations', sa.Column('work_package_id', sa.Integer(), sa.ForeignKey('work_packages.id'), nullable=True))
    op.add_column('stores_lot_reservations', sa.Column('planning_wbs_id', sa.Integer(), sa.ForeignKey('planning_wbs.id'), nullable=True))
    op.create_index('ix_stores_lot_reservations_work_package_id', 'stores_lot_reservations', ['work_package_id'])
    op.create_index('ix_stores_lot_reservations_planning_wbs_id', 'stores_lot_reservations', ['planning_wbs_id'])
    op.create_table('stores_reservation_reassignments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('reservation_id', sa.Integer(), sa.ForeignKey('stores_lot_reservations.id'), nullable=False),
        sa.Column('action_key', sa.String(120), nullable=False),
        sa.Column('old_work_package_id', sa.Integer(), nullable=True),
        sa.Column('new_work_package_id', sa.Integer(), nullable=True),
        sa.Column('old_planning_wbs_id', sa.Integer(), nullable=True),
        sa.Column('new_planning_wbs_id', sa.Integer(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', 'action_key', name='uq_stores_reservation_reassign_key'))

def downgrade():
    op.drop_table('stores_reservation_reassignments')
    op.drop_index('ix_stores_lot_reservations_planning_wbs_id', table_name='stores_lot_reservations')
    op.drop_index('ix_stores_lot_reservations_work_package_id', table_name='stores_lot_reservations')
    op.drop_column('stores_lot_reservations', 'planning_wbs_id')
    op.drop_column('stores_lot_reservations', 'work_package_id')
