"""Explicit contract obligation linkage for Stores issue requests; non-financial."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase8_contract_obligation_link'
down_revision = 'stores_phase7_scrap_disposal'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('stores_contract_obligation_links',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('material_request_id', sa.Integer(), sa.ForeignKey('stores_material_requests.id'), nullable=False),
        sa.Column('contract_id', sa.Integer(), sa.ForeignKey('contract_register.id'), nullable=False),
        sa.Column('obligation_id', sa.Integer(), sa.ForeignKey('contract_obligations.id'), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('material_request_id', name='uq_stores_one_contract_obligation_per_request'))
    op.create_index('ix_stores_contract_link_org_project', 'stores_contract_obligation_links', ['organization_id', 'project_id'])

def downgrade():
    op.drop_index('ix_stores_contract_link_org_project', table_name='stores_contract_obligation_links')
    op.drop_table('stores_contract_obligation_links')
