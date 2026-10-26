"""CM0107 module-owned contract amendment receipt projections.

Revision ID: cm0107
Revises: cm0105
"""
from alembic import op
import sqlalchemy as sa
revision='cm0107'
down_revision='cm0105'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('contract_consumer_projections',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contract_register.id'),nullable=False),
        sa.Column('amendment_id',sa.Integer(),sa.ForeignKey('contract_amendments.id'),nullable=False),
        sa.Column('destination',sa.String(35),nullable=False),
        sa.Column('contract_version',sa.Integer(),nullable=False),
        sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('received_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('received_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('amendment_id','destination'))
    op.create_index('ix_contract_consumer_scope','contract_consumer_projections',['organization_id','project_id'])
    op.create_index('ix_contract_consumer_contract','contract_consumer_projections',['contract_id'])

def downgrade():
    op.drop_index('ix_contract_consumer_contract',table_name='contract_consumer_projections')
    op.drop_index('ix_contract_consumer_scope',table_name='contract_consumer_projections')
    op.drop_table('contract_consumer_projections')
