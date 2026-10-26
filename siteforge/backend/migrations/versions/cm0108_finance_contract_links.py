"""Explicit Finance contract links. Revision ID: cm0108; Revises: cm0107."""
from alembic import op
import sqlalchemy as sa
revision='cm0108'
down_revision='cm0107'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('contract_finance_links',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contract_register.id'),nullable=False),
        sa.Column('finance_contract_id',sa.Integer(),sa.ForeignKey('finance_contracts.id'),nullable=False),
        sa.Column('linked_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('linked_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('contract_id'),sa.UniqueConstraint('finance_contract_id'))
    op.create_index('ix_finance_link_scope','contract_finance_links',['organization_id','project_id'])

def downgrade():
    op.drop_index('ix_finance_link_scope',table_name='contract_finance_links')
    op.drop_table('contract_finance_links')
