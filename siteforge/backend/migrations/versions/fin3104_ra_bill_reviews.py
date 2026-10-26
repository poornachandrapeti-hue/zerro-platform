"""Multi-line RA bill review and financial posting."""
import sqlalchemy as sa
from alembic import op
revision='fin3104'
down_revision='fin3103'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('finance_subcontract_bills',sa.Column('retention_amount',sa.Numeric(20,2),server_default='0',nullable=False))
    op.add_column('finance_subcontract_bills',sa.Column('advance_recovery_amount',sa.Numeric(20,2),server_default='0',nullable=False))
    op.add_column('finance_subcontract_bills',sa.Column('other_deduction_amount',sa.Numeric(20,2),server_default='0',nullable=False))
    op.add_column('finance_subcontract_bills',sa.Column('net_payable',sa.Numeric(20,2),server_default='0',nullable=False))
    op.add_column('finance_subcontract_bills',sa.Column('posted_at',sa.DateTime(timezone=True)))
    op.add_column('finance_subcontract_bills',sa.Column('posted_by',sa.Integer,sa.ForeignKey('users.id')))
    # Legacy single-measurement bills keep their source link; backfill once.
    op.create_table('finance_bill_lines',sa.Column('id',sa.Integer,primary_key=True),sa.Column('bill_id',sa.Integer,sa.ForeignKey('finance_subcontract_bills.id'),nullable=False),sa.Column('measurement_id',sa.Integer,sa.ForeignKey('finance_measurements.id'),nullable=False,unique=True),sa.Column('value_snapshot',sa.Numeric(20,2),nullable=False))
    op.create_index('ix_finance_bill_lines_bill_id','finance_bill_lines',['bill_id'])
    op.execute("INSERT INTO finance_bill_lines (bill_id,measurement_id,value_snapshot) SELECT id,measurement_id,gross_value FROM finance_subcontract_bills")
    op.execute('UPDATE finance_subcontract_bills SET net_payable=gross_value')
    op.create_table('finance_bill_decisions',sa.Column('id',sa.Integer,primary_key=True),sa.Column('bill_id',sa.Integer,sa.ForeignKey('finance_subcontract_bills.id'),nullable=False),sa.Column('actor_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('action',sa.String(40),nullable=False),sa.Column('reason',sa.Text,nullable=False),sa.Column('occurred_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_finance_bill_decisions_bill_id','finance_bill_decisions',['bill_id'])

def downgrade():
    op.drop_index('ix_finance_bill_decisions_bill_id',table_name='finance_bill_decisions');op.drop_table('finance_bill_decisions')
    op.drop_index('ix_finance_bill_lines_bill_id',table_name='finance_bill_lines');op.drop_table('finance_bill_lines')
    for col in ('posted_by','posted_at','net_payable','other_deduction_amount','advance_recovery_amount','retention_amount'):op.drop_column('finance_subcontract_bills',col)
