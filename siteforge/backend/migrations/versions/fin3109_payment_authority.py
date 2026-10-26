"""Financial payment approval authority limits (Phase 31.10)."""
import sqlalchemy as sa
from alembic import op
revision='fin3109'
down_revision='fin3108'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('finance_payment_approval_limits',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('payment_type',sa.String(24),nullable=False),
        sa.Column('maximum_amount',sa.Numeric(20,2),nullable=False),
        sa.Column('active',sa.Boolean,nullable=False,server_default=sa.text('true')),
        sa.Column('configured_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('configured_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('project_id','user_id','currency','payment_type'))
    op.create_index('ix_finance_payment_approval_limits_project_id','finance_payment_approval_limits',['project_id'])
    op.create_index('ix_finance_payment_approval_limits_user_id','finance_payment_approval_limits',['user_id'])

def downgrade():
    op.drop_table('finance_payment_approval_limits')
