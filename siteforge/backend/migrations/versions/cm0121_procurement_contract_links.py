"""Governed purchase-order links; Revision ID: cm0121; Revises: cm0118."""
from alembic import op
import sqlalchemy as sa
revision = 'cm0121'
down_revision = 'cm0118'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('contract_procurement_links',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('organization_id', sa.Integer, sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('project_id', sa.Integer, sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('contract_id', sa.Integer, sa.ForeignKey('contract_register.id'), nullable=False),
        sa.Column('contract_version_id', sa.Integer, sa.ForeignKey('contract_versions.id'), nullable=False),
        sa.Column('purchase_order_id', sa.Integer, sa.ForeignKey('purchase_orders.id'), nullable=False),
        sa.Column('linked_by', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('linked_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('purchase_order_id'))
    op.create_index('ix_contract_procurement_links_contract_id', 'contract_procurement_links', ['contract_id'])
    op.create_index('ix_contract_procurement_links_project_id', 'contract_procurement_links', ['project_id'])
    op.create_index('ix_contract_procurement_links_organization_id', 'contract_procurement_links', ['organization_id'])

def downgrade():
    op.drop_index('ix_contract_procurement_links_organization_id', table_name='contract_procurement_links')
    op.drop_index('ix_contract_procurement_links_project_id', table_name='contract_procurement_links')
    op.drop_index('ix_contract_procurement_links_contract_id', table_name='contract_procurement_links')
    op.drop_table('contract_procurement_links')
