"""Monthly financial period close with auditable reopen events."""
import sqlalchemy as sa
from alembic import op
revision='fin3112'
down_revision='fin3111'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('finance_periods',
      sa.Column('id',sa.Integer,primary_key=True),
      sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
      sa.Column('currency',sa.String(3),nullable=False),
      sa.Column('period_start',sa.DateTime(timezone=True),nullable=False),
      sa.Column('status',sa.String(16),nullable=False),
      sa.Column('closed_by',sa.Integer,sa.ForeignKey('users.id')),
      sa.Column('closed_at',sa.DateTime(timezone=True)),
      sa.UniqueConstraint('project_id','currency','period_start',name='uq_finance_period'))
    op.create_index('ix_finance_periods_project','finance_periods',['project_id'])
    op.create_table('finance_period_decisions',
      sa.Column('id',sa.Integer,primary_key=True),
      sa.Column('period_id',sa.Integer,sa.ForeignKey('finance_periods.id'),nullable=False),
      sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
      sa.Column('action',sa.String(16),nullable=False),
      sa.Column('reason',sa.Text,nullable=False),
      sa.Column('actor_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
      sa.Column('recorded_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_finance_period_decisions_period','finance_period_decisions',['period_id'])
    op.create_index('ix_finance_period_decisions_project','finance_period_decisions',['project_id'])

def downgrade():
    op.drop_table('finance_period_decisions')
    op.drop_table('finance_periods')
