"""Direct expenses, contract variations and advance/retention balances."""
import sqlalchemy as sa
from alembic import op
revision='fin3106'
down_revision='fin3105'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('finance_direct_expenses',
        sa.Column('id',sa.Integer,primary_key=True),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('number',sa.String(80),nullable=False),sa.Column('cost_code_id',sa.Integer,sa.ForeignKey('finance_cost_codes.id'),nullable=False),
        sa.Column('source_reference',sa.String(160),nullable=False),sa.Column('description',sa.Text,nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),sa.Column('amount',sa.Numeric(20,2),nullable=False),
        sa.Column('status',sa.String(32),nullable=False),sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('approved_by',sa.Integer,sa.ForeignKey('users.id')),sa.Column('approved_at',sa.DateTime(timezone=True)),
        sa.Column('evidence_reference',sa.Text,nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('project_id','number'),sa.UniqueConstraint('project_id','source_reference'))
    op.create_index('ix_finance_direct_expenses_project_id','finance_direct_expenses',['project_id'])
    op.create_table('finance_variations',
        sa.Column('id',sa.Integer,primary_key=True),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('contract_id',sa.Integer,sa.ForeignKey('finance_contracts.id'),nullable=False),
        sa.Column('number',sa.String(80),nullable=False),sa.Column('description',sa.Text,nullable=False),
        sa.Column('cost_impact',sa.Numeric(20,2),nullable=False),sa.Column('revenue_impact',sa.Numeric(20,2),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),sa.Column('status',sa.String(32),nullable=False),
        sa.Column('evidence_reference',sa.Text,nullable=False),sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('approved_by',sa.Integer,sa.ForeignKey('users.id')),sa.Column('approved_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('project_id','number'))
    op.create_index('ix_finance_variations_project_id','finance_variations',['project_id'])
    op.create_table('finance_balance_entries',
        sa.Column('id',sa.Integer,primary_key=True),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('contract_id',sa.Integer,sa.ForeignKey('finance_contracts.id'),nullable=False),
        sa.Column('reference',sa.String(120),nullable=False),sa.Column('balance_type',sa.String(32),nullable=False),
        sa.Column('movement',sa.String(16),nullable=False),sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('amount',sa.Numeric(20,2),nullable=False),sa.Column('evidence_reference',sa.Text,nullable=False),
        sa.Column('recorded_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('recorded_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('project_id','reference'))
    op.create_index('ix_finance_balance_entries_project_id','finance_balance_entries',['project_id'])

def downgrade():
    for table in ('finance_balance_entries','finance_variations','finance_direct_expenses'):
        op.drop_index('ix_'+table+'_project_id',table_name=table)
        op.drop_table(table)
