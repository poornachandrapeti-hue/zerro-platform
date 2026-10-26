"""Contract BOQ and source-gated measurement certification (Phase 31.3)."""
import sqlalchemy as sa
from alembic import op
revision='fin3103'
down_revision='fin3102'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('finance_contracts',
      sa.Column('id',sa.Integer,primary_key=True),sa.Column('organization_id',sa.Integer,sa.ForeignKey('organizations.id'),nullable=False),
      sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),sa.Column('number',sa.String(80),nullable=False),
      sa.Column('contract_type',sa.String(40),nullable=False),sa.Column('counterparty_company_id',sa.Integer,sa.ForeignKey('companies.id'),nullable=False),
      sa.Column('currency',sa.String(3),nullable=False),sa.Column('original_value',sa.Numeric(20,2),nullable=False),
      sa.Column('status',sa.String(30),nullable=False),sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
      sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('project_id','number'))
    op.create_table('finance_boq_lines',sa.Column('id',sa.Integer,primary_key=True),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
      sa.Column('contract_id',sa.Integer,sa.ForeignKey('finance_contracts.id'),nullable=False),sa.Column('code',sa.String(80),nullable=False),
      sa.Column('description',sa.String(240),nullable=False),sa.Column('activity_id',sa.Integer,sa.ForeignKey('construction_activities.id'),nullable=False),
      sa.Column('unit',sa.String(40),nullable=False),sa.Column('quantity',sa.Numeric(18,3),nullable=False),
      sa.Column('unit_rate',sa.Numeric(20,2),nullable=False),sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.UniqueConstraint('contract_id','code'))
    op.create_table('finance_measurements',sa.Column('id',sa.Integer,primary_key=True),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
      sa.Column('contract_id',sa.Integer,sa.ForeignKey('finance_contracts.id'),nullable=False),sa.Column('boq_line_id',sa.Integer,sa.ForeignKey('finance_boq_lines.id'),nullable=False),
      sa.Column('number',sa.String(80),nullable=False),sa.Column('claimed_quantity',sa.Numeric(18,3),nullable=False),
      sa.Column('certified_quantity',sa.Numeric(18,3),nullable=False),sa.Column('unit_rate_snapshot',sa.Numeric(20,2),nullable=False),
      sa.Column('status',sa.String(30),nullable=False),sa.Column('evidence_note',sa.Text,nullable=False),
      sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('certified_by',sa.Integer,sa.ForeignKey('users.id')),
      sa.Column('certified_at',sa.DateTime(timezone=True)),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('project_id','number'))
    op.create_table('finance_subcontract_bills',sa.Column('id',sa.Integer,primary_key=True),sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
      sa.Column('contract_id',sa.Integer,sa.ForeignKey('finance_contracts.id'),nullable=False),sa.Column('measurement_id',sa.Integer,sa.ForeignKey('finance_measurements.id'),nullable=False,unique=True),
      sa.Column('number',sa.String(80),nullable=False),sa.Column('gross_value',sa.Numeric(20,2),nullable=False),sa.Column('status',sa.String(30),nullable=False),
      sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('project_id','number'))
    for table in ('finance_contracts','finance_boq_lines','finance_measurements','finance_subcontract_bills'):
        op.create_index('ix_'+table+'_project_id',table,['project_id'])

def downgrade():
    for table in ('finance_subcontract_bills','finance_measurements','finance_boq_lines','finance_contracts'):
        op.drop_table(table)
