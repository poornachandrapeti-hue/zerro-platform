"""Structured contract scope and commercial terms.

Revision ID: cm0109
Revises: cm0108
"""
from alembic import op
import sqlalchemy as sa
revision='cm0109'
down_revision='cm0108'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('contract_scope_items',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('contract_id',sa.Integer,sa.ForeignKey('contract_register.id'),nullable=False),
        sa.Column('version_id',sa.Integer,sa.ForeignKey('contract_versions.id'),nullable=False),
        sa.Column('item_code',sa.String(80),nullable=False),
        sa.Column('item_type',sa.String(40),nullable=False),
        sa.Column('description',sa.Text,nullable=False),
        sa.Column('responsible_company_id',sa.Integer,sa.ForeignKey('companies.id')),
        sa.Column('responsible_user_id',sa.Integer,sa.ForeignKey('users.id')),
        sa.Column('reviewer_user_id',sa.Integer,sa.ForeignKey('users.id')),
        sa.Column('due_at',sa.DateTime(timezone=True)),
        sa.Column('required_evidence',sa.Text),
        sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('version_id','item_code'))
    op.create_index('ix_contract_scope_items_contract_id','contract_scope_items',['contract_id'])
    op.create_index('ix_contract_scope_items_version_id','contract_scope_items',['version_id'])
    op.create_table('contract_term_versions',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('contract_id',sa.Integer,sa.ForeignKey('contract_register.id'),nullable=False),
        sa.Column('version_id',sa.Integer,sa.ForeignKey('contract_versions.id'),nullable=False),
        sa.Column('term_key',sa.String(80),nullable=False),
        sa.Column('clause_reference',sa.String(120)),
        sa.Column('value',sa.JSON,nullable=False),
        sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('version_id','term_key'))
    op.create_index('ix_contract_term_versions_contract_id','contract_term_versions',['contract_id'])
    op.create_index('ix_contract_term_versions_version_id','contract_term_versions',['version_id'])

def downgrade():
    op.drop_index('ix_contract_term_versions_version_id',table_name='contract_term_versions')
    op.drop_index('ix_contract_term_versions_contract_id',table_name='contract_term_versions')
    op.drop_table('contract_term_versions')
    op.drop_index('ix_contract_scope_items_version_id',table_name='contract_scope_items')
    op.drop_index('ix_contract_scope_items_contract_id',table_name='contract_scope_items')
    op.drop_table('contract_scope_items')
