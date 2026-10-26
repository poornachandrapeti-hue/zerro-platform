"""Financial cost codes and revisioned budgets."""
import sqlalchemy as sa
from alembic import op
revision='fin3101'
down_revision='p18a1c4e7f725'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('finance_cost_codes',
      sa.Column('id',sa.Integer,primary_key=True),
      sa.Column('organization_id',sa.Integer,sa.ForeignKey('organizations.id'),nullable=False),
      sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
      sa.Column('code',sa.String(80),nullable=False),
      sa.Column('description',sa.String(240),nullable=False),
      sa.Column('category',sa.String(64),nullable=False),
      sa.Column('discipline_id',sa.Integer,sa.ForeignKey('disciplines.id')),
      sa.UniqueConstraint('project_id','code'))
    op.create_index('ix_finance_cost_codes_project_id','finance_cost_codes',['project_id'])
    op.create_index('ix_finance_cost_codes_organization_id','finance_cost_codes',['organization_id'])
    op.create_table('finance_budgets',
      sa.Column('id',sa.Integer,primary_key=True),
      sa.Column('organization_id',sa.Integer,sa.ForeignKey('organizations.id'),nullable=False),
      sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
      sa.Column('code',sa.String(80),nullable=False),
      sa.Column('revision',sa.Integer,nullable=False),
      sa.Column('cost_code_id',sa.Integer,sa.ForeignKey('finance_cost_codes.id'),nullable=False),
      sa.Column('description',sa.String(240),nullable=False),
      sa.Column('currency',sa.String(3),nullable=False),
      sa.Column('proposed_amount',sa.Numeric(20,2),nullable=False),
      sa.Column('forecast_remaining',sa.Numeric(20,2)),
      sa.Column('status',sa.String(30),nullable=False),
      sa.Column('submitted_by',sa.Integer,sa.ForeignKey('users.id')),
      sa.Column('approved_by',sa.Integer,sa.ForeignKey('users.id')),
      sa.Column('approved_at',sa.DateTime(timezone=True)),
      sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
      sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
      sa.Column('decision_reason',sa.Text,nullable=False),
      sa.UniqueConstraint('project_id','code','revision'))
    op.create_index('ix_finance_budgets_project_id','finance_budgets',['project_id'])
    op.create_index('ix_finance_budgets_organization_id','finance_budgets',['organization_id'])

def downgrade():
    op.drop_table('finance_budgets')
    op.drop_table('finance_cost_codes')
