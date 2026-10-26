"""Controlled correspondence ledger. Revision ID cm0115, revises cm0114."""
from alembic import op
import sqlalchemy as sa
revision='cm0115'
down_revision='cm0114'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('contract_correspondence_ledger',
       sa.Column('id',sa.Integer,primary_key=True),
       sa.Column('organization_id',sa.Integer,sa.ForeignKey('organizations.id'),nullable=False),
       sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
       sa.Column('contract_id',sa.Integer,sa.ForeignKey('contract_register.id'),nullable=False),
       sa.Column('version_id',sa.Integer,sa.ForeignKey('contract_versions.id'),nullable=False),
       sa.Column('number',sa.String(80),nullable=False),
       sa.Column('category',sa.String(40),nullable=False),
       sa.Column('subject',sa.String(240),nullable=False),
       sa.Column('content',sa.Text,nullable=False),
       sa.Column('sender_company_id',sa.Integer,sa.ForeignKey('companies.id'),nullable=False),
       sa.Column('recipient_company_id',sa.Integer,sa.ForeignKey('companies.id'),nullable=False),
       sa.Column('linked_claim_id',sa.Integer,sa.ForeignKey('contract_claims.id')),
       sa.Column('response_due_at',sa.DateTime(timezone=True)),
       sa.Column('status',sa.String(32),nullable=False),
       sa.Column('approval_evidence',sa.Text),
       sa.Column('approved_by',sa.Integer,sa.ForeignKey('users.id')),
       sa.Column('approved_at',sa.DateTime(timezone=True)),
       sa.Column('delivery_method',sa.String(80)),
       sa.Column('issue_at',sa.DateTime(timezone=True)),
       sa.Column('dispatch_reference',sa.String(240)),
       sa.Column('dispatch_evidence',sa.Text),
       sa.Column('receipt_at',sa.DateTime(timezone=True)),
       sa.Column('receipt_evidence',sa.Text),
       sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
       sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
       sa.UniqueConstraint('contract_id','number'))
    op.create_index('ix_contract_correspondence_ledger_contract_id','contract_correspondence_ledger',['contract_id'])
    op.create_index('ix_contract_correspondence_ledger_project_id','contract_correspondence_ledger',['project_id'])
    op.create_index('ix_contract_correspondence_ledger_organization_id','contract_correspondence_ledger',['organization_id'])

def downgrade():
    op.drop_index('ix_contract_correspondence_ledger_organization_id',table_name='contract_correspondence_ledger')
    op.drop_index('ix_contract_correspondence_ledger_project_id',table_name='contract_correspondence_ledger')
    op.drop_index('ix_contract_correspondence_ledger_contract_id',table_name='contract_correspondence_ledger')
    op.drop_table('contract_correspondence_ledger')
