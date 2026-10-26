"""Dedicated contractual obligations with trigger-based deadlines.
Revision ID: cm0110
Revises: cm0109
"""
from alembic import op
import sqlalchemy as sa
revision='cm0110'
down_revision='cm0109'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('contract_obligations',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contract_register.id'),nullable=False),
        sa.Column('version_id',sa.Integer(),sa.ForeignKey('contract_versions.id'),nullable=False),
        sa.Column('number',sa.String(80),nullable=False),
        sa.Column('clause_reference',sa.String(120)),
        sa.Column('description',sa.Text(),nullable=False),
        sa.Column('responsible_company_id',sa.Integer(),sa.ForeignKey('companies.id'),nullable=False),
        sa.Column('owner_user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('trigger_name',sa.String(120)),
        sa.Column('trigger_at',sa.DateTime(timezone=True)),
        sa.Column('due_days',sa.Integer()),
        sa.Column('due_at',sa.DateTime(timezone=True)),
        sa.Column('required_evidence',sa.Text()),
        sa.Column('acceptance_required',sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column('status',sa.String(40),nullable=False,server_default='Not Started'),
        sa.Column('evidence',sa.Text()),
        sa.Column('decision_evidence',sa.Text()),
        sa.Column('decided_by',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('decided_at',sa.DateTime(timezone=True)),
        sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('contract_id','number'))
    op.create_index('ix_contract_obligations_org_project','contract_obligations',['organization_id','project_id'])
    op.create_index('ix_contract_obligations_due','contract_obligations',['due_at'])

def downgrade():
    op.drop_index('ix_contract_obligations_due',table_name='contract_obligations')
    op.drop_index('ix_contract_obligations_org_project',table_name='contract_obligations')
    op.drop_table('contract_obligations')
