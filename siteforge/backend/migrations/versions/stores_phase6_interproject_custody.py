"""Add destination-project custody tracking; no inventory ledger changes."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase6_interproject_custody'
down_revision = 'stores_phase6_transfer_discrepancy'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('stores_transfers', sa.Column('destination_project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=True))
    op.add_column('stores_transfers', sa.Column('destination_accepted_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('stores_transfers', sa.Column('destination_acceptance_evidence', sa.Text(), nullable=False, server_default=''))
    op.execute('UPDATE stores_transfers SET destination_project_id = project_id WHERE destination_project_id IS NULL')
    op.create_index('ix_stores_transfers_destination_project_id', 'stores_transfers', ['destination_project_id'])

def downgrade():
    op.drop_index('ix_stores_transfers_destination_project_id', table_name='stores_transfers')
    op.drop_column('stores_transfers', 'destination_acceptance_evidence')
    op.drop_column('stores_transfers', 'destination_accepted_by')
    op.drop_column('stores_transfers', 'destination_project_id')
