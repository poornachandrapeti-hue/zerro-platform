"""Transfer company custody declarations; not title or stock movements."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase6_custody_companies'
down_revision = 'stores_phase6_interproject_custody'
branch_labels = None
depends_on = None

def upgrade():
    for name in ('declared_owner_company_id', 'source_custodian_company_id', 'destination_custodian_company_id'):
        op.add_column('stores_transfers', sa.Column(name, sa.Integer(), sa.ForeignKey('companies.id'), nullable=True))
    op.add_column('stores_transfers', sa.Column('custody_confirmed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('stores_transfers', sa.Column('custody_confirmation_evidence', sa.Text(), nullable=False, server_default=''))
    op.add_column('stores_transfers', sa.Column('custody_confirmed_at', sa.DateTime(timezone=True), nullable=True))

def downgrade():
    for name in ('custody_confirmed_at', 'custody_confirmation_evidence', 'custody_confirmed_by',
                 'destination_custodian_company_id', 'source_custodian_company_id', 'declared_owner_company_id'):
        op.drop_column('stores_transfers', name)
