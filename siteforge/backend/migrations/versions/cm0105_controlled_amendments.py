"""Controlled amendments and transactional downstream delivery records."""
from alembic import op
import sqlalchemy as sa
revision='cm0105'
down_revision='cm0104'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('contract_amendments',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('contract_id',sa.Integer,sa.ForeignKey('contract_register.id'),nullable=False),
        sa.Column('variation_id',sa.Integer,sa.ForeignKey('contract_records.id'),nullable=False),
        sa.Column('amendment_number',sa.String(80),nullable=False),
        sa.Column('delta_value',sa.Numeric(20,2),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('status',sa.String(35),nullable=False),
        sa.Column('prepared_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('approved_by',sa.Integer,sa.ForeignKey('users.id')),
        sa.Column('executed_by',sa.Integer,sa.ForeignKey('users.id')),
        sa.Column('approval_reason',sa.Text),
        sa.Column('execution_evidence',sa.Text),
        sa.Column('effective_version_id',sa.Integer,sa.ForeignKey('contract_versions.id')),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('effective_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('variation_id'),sa.UniqueConstraint('contract_id','amendment_number'))
    op.create_index('ix_contract_amendments_contract_id','contract_amendments',['contract_id'])
    op.create_index('ix_contract_amendments_variation_id','contract_amendments',['variation_id'])
    op.create_table('contract_module_deliveries',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('amendment_id',sa.Integer,sa.ForeignKey('contract_amendments.id'),nullable=False),
        sa.Column('destination',sa.String(35),nullable=False),
        sa.Column('status',sa.String(25),nullable=False),
        sa.Column('payload',sa.JSON,nullable=False),
        sa.Column('acknowledged_by',sa.Integer,sa.ForeignKey('users.id')),
        sa.Column('receipt_reference',sa.String(160)),
        sa.Column('acknowledged_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('amendment_id','destination'))
    op.create_index('ix_contract_module_deliveries_amendment_id','contract_module_deliveries',['amendment_id'])

def downgrade():
    op.drop_index('ix_contract_module_deliveries_amendment_id',table_name='contract_module_deliveries')
    op.drop_table('contract_module_deliveries')
    op.drop_index('ix_contract_amendments_variation_id',table_name='contract_amendments')
    op.drop_index('ix_contract_amendments_contract_id',table_name='contract_amendments')
    op.drop_table('contract_amendments')
