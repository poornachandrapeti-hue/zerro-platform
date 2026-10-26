"""Private partner document ACL. Revision ID: cm0118; Revises: cm0117."""
from alembic import op
import sqlalchemy as sa
revision='cm0118'
down_revision='cm0117'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('contract_partner_documents',
      sa.Column('id',sa.Integer(),primary_key=True),
      sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contract_register.id'),nullable=False),
      sa.Column('company_id',sa.Integer(),sa.ForeignKey('companies.id'),nullable=False),
      sa.Column('contract_version_id',sa.Integer(),sa.ForeignKey('contract_versions.id'),nullable=False),
      sa.Column('document_key',sa.String(160),nullable=False),
      sa.Column('revision',sa.Integer(),nullable=False),
      sa.Column('display_name',sa.String(240),nullable=False),
      sa.Column('document_class',sa.String(50),nullable=False),
      sa.Column('private_storage_key',sa.String(500),nullable=False),
      sa.Column('content_sha256',sa.String(64),nullable=False),
      sa.Column('published_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
      sa.Column('published_at',sa.DateTime(timezone=True),nullable=False),
      sa.Column('expires_at',sa.DateTime(timezone=True)),
      sa.Column('revoked_at',sa.DateTime(timezone=True)),
      sa.UniqueConstraint('contract_id','company_id','document_key','revision'))
    op.create_index('ix_contract_partner_documents_contract_id','contract_partner_documents',['contract_id'])
    op.create_index('ix_contract_partner_documents_company_id','contract_partner_documents',['company_id'])

def downgrade():
    op.drop_index('ix_contract_partner_documents_company_id',table_name='contract_partner_documents')
    op.drop_index('ix_contract_partner_documents_contract_id',table_name='contract_partner_documents')
    op.drop_table('contract_partner_documents')
