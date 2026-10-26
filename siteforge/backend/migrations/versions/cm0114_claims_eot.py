"""Dedicated claim and EOT ledger. Revision ID cm0114, revises cm0110."""
from alembic import op
import sqlalchemy as sa
revision='cm0114'
down_revision='cm0110'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('contract_claims',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('contract_id',sa.Integer,sa.ForeignKey('contract_register.id'),nullable=False),
        sa.Column('version_id',sa.Integer,sa.ForeignKey('contract_versions.id'),nullable=False),
        sa.Column('number',sa.String(80),nullable=False),
        sa.Column('category',sa.String(50),nullable=False),
        sa.Column('description',sa.Text,nullable=False),
        sa.Column('event_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('clause_reference',sa.String(160)),
        sa.Column('source_reference',sa.Text),
        sa.Column('notice_required',sa.Boolean,nullable=False),
        sa.Column('notice_due_at',sa.DateTime(timezone=True)),
        sa.Column('notice_sent_at',sa.DateTime(timezone=True)),
        sa.Column('notice_evidence',sa.Text),
        sa.Column('submission_due_at',sa.DateTime(timezone=True)),
        sa.Column('requested_amount',sa.Numeric(20,2)),
        sa.Column('currency',sa.String(3)),
        sa.Column('requested_eot_days',sa.Integer),
        sa.Column('calculation_evidence',sa.Text),
        sa.Column('submission_evidence',sa.Text),
        sa.Column('counterparty_response',sa.Text),
        sa.Column('agreed_amount',sa.Numeric(20,2)),
        sa.Column('agreed_eot_days',sa.Integer),
        sa.Column('decision_evidence',sa.Text),
        sa.Column('status',sa.String(40),nullable=False),
        sa.Column('owner_user_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('contract_id','number'))
    op.create_index('ix_contract_claims_project_id','contract_claims',['project_id'])
    op.create_index('ix_contract_claims_organization_id','contract_claims',['organization_id'])
    op.create_index('ix_contract_claims_contract_id','contract_claims',['contract_id'])

def downgrade():
    op.drop_index('ix_contract_claims_contract_id',table_name='contract_claims')
    op.drop_index('ix_contract_claims_organization_id',table_name='contract_claims')
    op.drop_index('ix_contract_claims_project_id',table_name='contract_claims')
    op.drop_table('contract_claims')
