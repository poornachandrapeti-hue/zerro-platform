"""Financial payment requests and externally recorded settlements."""
import sqlalchemy as sa
from alembic import op
revision='fin3107'
down_revision='fin3106'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('finance_payment_requests',
        sa.Column('id',sa.Integer,primary_key=True),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('bill_id',sa.Integer,sa.ForeignKey('finance_subcontract_bills.id'),nullable=False),
        sa.Column('number',sa.String(80),nullable=False),sa.Column('amount',sa.Numeric(20,2),nullable=False),sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('due_date',sa.DateTime(timezone=True)),sa.Column('status',sa.String(32),nullable=False),
        sa.Column('evidence_reference',sa.Text,nullable=False),sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('approved_by',sa.Integer,sa.ForeignKey('users.id')),sa.Column('approved_at',sa.DateTime(timezone=True)),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('project_id','number'))
    op.create_index('ix_finance_payment_requests_project_id','finance_payment_requests',['project_id'])
    op.create_index('ix_finance_payment_requests_bill_id','finance_payment_requests',['bill_id'])
    op.create_table('finance_payment_records',
        sa.Column('id',sa.Integer,primary_key=True),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('payment_request_id',sa.Integer,sa.ForeignKey('finance_payment_requests.id'),nullable=False),
        sa.Column('amount',sa.Numeric(20,2),nullable=False),sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('paid_at',sa.DateTime(timezone=True),nullable=False),sa.Column('transaction_reference',sa.String(160),nullable=False),
        sa.Column('evidence_reference',sa.Text,nullable=False),sa.Column('recorded_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('project_id','transaction_reference'))
    op.create_index('ix_finance_payment_records_project_id','finance_payment_records',['project_id'])
    op.create_index('ix_finance_payment_records_payment_request_id','finance_payment_records',['payment_request_id'])

def downgrade():
    op.drop_table('finance_payment_records')
    op.drop_table('finance_payment_requests')
