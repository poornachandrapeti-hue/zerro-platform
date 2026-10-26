"""Contracts integrated register foundation, partner shares and source-linked records.

Revision ID: cm0101
Revises: fin3114
"""
from alembic import op
import sqlalchemy as sa
revision='cm0101'
down_revision='fin3114'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('contract_register',
        sa.Column('id',sa.Integer(),primary_key=True),sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('number',sa.String(80),nullable=False),sa.Column('title',sa.String(240),nullable=False),sa.Column('contract_type',sa.String(40),nullable=False),
        sa.Column('contracting_company_id',sa.Integer(),sa.ForeignKey('companies.id'),nullable=False),sa.Column('counterparty_company_id',sa.Integer(),sa.ForeignKey('companies.id'),nullable=False),sa.Column('manager_user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('scope',sa.Text(),nullable=False),sa.Column('currency',sa.String(3)),sa.Column('original_value',sa.Numeric(20,2)),sa.Column('effective_at',sa.DateTime(timezone=True)),sa.Column('expires_at',sa.DateTime(timezone=True)),
        sa.Column('lifecycle',sa.String(45),nullable=False),sa.Column('approval_state',sa.String(40),nullable=False),sa.Column('current_version',sa.Integer(),nullable=False),sa.Column('published_version',sa.Integer()),sa.Column('execution_evidence',sa.Text()),sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('organization_id','number'))
    op.create_index('ix_contract_register_project_id','contract_register',['project_id'])
    op.create_index('ix_contract_register_organization_id','contract_register',['organization_id'])
    op.create_table('contract_versions',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contract_register.id'),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('snapshot',sa.JSON(),nullable=False),sa.Column('state',sa.String(30),nullable=False),sa.Column('reason',sa.Text(),nullable=False),sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('contract_id','version'))
    op.create_index('ix_contract_versions_contract_id','contract_versions',['contract_id'])
    op.create_table('contract_boq_version_lines',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contract_register.id'),nullable=False),sa.Column('version_id',sa.Integer(),sa.ForeignKey('contract_versions.id'),nullable=False),sa.Column('code',sa.String(80),nullable=False),sa.Column('description',sa.Text(),nullable=False),sa.Column('unit',sa.String(40),nullable=False),sa.Column('quantity',sa.Numeric(20,4),nullable=False),sa.Column('rate',sa.Numeric(20,2),nullable=False),sa.Column('currency',sa.String(3),nullable=False),sa.Column('pricing_type',sa.String(35),nullable=False),sa.UniqueConstraint('version_id','code'))
    op.create_index('ix_contract_boq_version_lines_contract_id','contract_boq_version_lines',['contract_id'])
    op.create_index('ix_contract_boq_version_lines_version_id','contract_boq_version_lines',['version_id'])
    op.create_table('contract_records',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contract_register.id'),nullable=False),sa.Column('version_id',sa.Integer(),sa.ForeignKey('contract_versions.id')),sa.Column('category',sa.String(35),nullable=False),sa.Column('number',sa.String(80),nullable=False),sa.Column('summary',sa.Text(),nullable=False),sa.Column('status',sa.String(40),nullable=False),sa.Column('due_at',sa.DateTime(timezone=True)),sa.Column('amount',sa.Numeric(20,2)),sa.Column('currency',sa.String(3)),sa.Column('evidence',sa.Text()),sa.Column('details',sa.JSON(),nullable=False),sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('contract_id','category','number'))
    op.create_index('ix_contract_records_contract_id','contract_records',['contract_id'])
    op.create_index('ix_contract_records_category','contract_records',['category'])
    op.create_table('contract_partner_shares',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contract_register.id'),nullable=False),sa.Column('company_id',sa.Integer(),sa.ForeignKey('companies.id'),nullable=False),sa.Column('published_version',sa.Integer(),nullable=False),sa.Column('can_submit',sa.Boolean(),nullable=False),sa.Column('active',sa.Boolean(),nullable=False),sa.Column('shared_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('contract_id','company_id'))
    op.create_index('ix_contract_partner_shares_contract_id','contract_partner_shares',['contract_id'])
    op.create_index('ix_contract_partner_shares_company_id','contract_partner_shares',['company_id'])
    op.create_table('contract_audit_events',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contract_register.id'),nullable=False),sa.Column('actor_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('action',sa.String(80),nullable=False),sa.Column('detail',sa.JSON(),nullable=False),sa.Column('at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_contract_audit_events_contract_id','contract_audit_events',['contract_id'])
    op.create_table('contract_financial_legacy_map',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('finance_contract_id',sa.Integer(),sa.ForeignKey('finance_contracts.id'),nullable=False,unique=True),sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contract_register.id'),nullable=False),sa.Column('version_id',sa.Integer(),sa.ForeignKey('contract_versions.id'),nullable=False),sa.Column('mapped_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('mapped_at',sa.DateTime(timezone=True),nullable=False))

def downgrade():
    for name in ('contract_financial_legacy_map','contract_audit_events','contract_partner_shares','contract_records','contract_boq_version_lines','contract_versions','contract_register'):
        op.drop_table(name)
