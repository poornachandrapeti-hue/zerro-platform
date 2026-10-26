"""Client claims, client certification, externally recorded collections."""
import sqlalchemy as sa
from alembic import op
revision='fin3105'
down_revision='fin3104'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('finance_client_claims',sa.Column('id',sa.Integer,primary_key=True),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),sa.Column('contract_id',sa.Integer,sa.ForeignKey('finance_contracts.id'),nullable=False),sa.Column('number',sa.String(80),nullable=False),sa.Column('billing_period',sa.String(40),nullable=False),sa.Column('amount',sa.Numeric(20,2),nullable=False),sa.Column('certified_value',sa.Numeric(20,2),nullable=False,server_default='0'),sa.Column('currency',sa.String(3),nullable=False),sa.Column('status',sa.String(36),nullable=False),sa.Column('evidence_reference',sa.Text,nullable=False),sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('certified_by',sa.Integer,sa.ForeignKey('users.id')),sa.Column('certified_at',sa.DateTime(timezone=True)),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('project_id','number'))
    op.create_index('ix_finance_client_claims_project_id','finance_client_claims',['project_id'])
    op.create_table('finance_client_claim_lines',sa.Column('id',sa.Integer,primary_key=True),sa.Column('claim_id',sa.Integer,sa.ForeignKey('finance_client_claims.id'),nullable=False),sa.Column('measurement_id',sa.Integer,sa.ForeignKey('finance_measurements.id'),nullable=False,unique=True),sa.Column('value_snapshot',sa.Numeric(20,2),nullable=False))
    op.create_index('ix_finance_client_claim_lines_claim_id','finance_client_claim_lines',['claim_id'])
    op.create_table('finance_client_collections',sa.Column('id',sa.Integer,primary_key=True),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),sa.Column('claim_id',sa.Integer,sa.ForeignKey('finance_client_claims.id'),nullable=False),sa.Column('amount',sa.Numeric(20,2),nullable=False),sa.Column('currency',sa.String(3),nullable=False),sa.Column('received_at',sa.DateTime(timezone=True),nullable=False),sa.Column('transaction_reference',sa.String(120),nullable=False),sa.Column('evidence_reference',sa.Text,nullable=False),sa.Column('recorded_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('project_id','transaction_reference'))
    op.create_index('ix_finance_client_collections_project_id','finance_client_collections',['project_id'])
    op.create_index('ix_finance_client_collections_claim_id','finance_client_collections',['claim_id'])
    op.create_table('finance_client_claim_decisions',sa.Column('id',sa.Integer,primary_key=True),sa.Column('claim_id',sa.Integer,sa.ForeignKey('finance_client_claims.id'),nullable=False),sa.Column('actor_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('action',sa.String(40),nullable=False),sa.Column('note',sa.Text,nullable=False),sa.Column('occurred_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_finance_client_claim_decisions_claim_id','finance_client_claim_decisions',['claim_id'])

def downgrade():
    for table,idx in [('finance_client_claim_decisions','ix_finance_client_claim_decisions_claim_id'),('finance_client_collections','ix_finance_client_collections_claim_id'),('finance_client_claim_lines','ix_finance_client_claim_lines_claim_id'),('finance_client_claims','ix_finance_client_claims_project_id')]:
        op.drop_index(idx,table_name=table)
        if table=='finance_client_collections':op.drop_index('ix_finance_client_collections_project_id',table_name=table)
        op.drop_table(table)
