"""Partner company for issue requests, preserving internal pre-existing rows."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase4_partner_issue_requests'
down_revision = 'stores_phase4_request_lot_allocation'
branch_labels = None
depends_on = None
def upgrade():
    op.add_column('stores_material_requests', sa.Column('requester_company_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_stores_issue_request_company', 'stores_material_requests', 'companies', ['requester_company_id'], ['id'])
    op.create_index('ix_stores_issue_request_company', 'stores_material_requests', ['requester_company_id'])
def downgrade():
    op.drop_index('ix_stores_issue_request_company', table_name='stores_material_requests')
    op.drop_constraint('fk_stores_issue_request_company', 'stores_material_requests', type_='foreignkey')
    op.drop_column('stores_material_requests', 'requester_company_id')
