"""Compensating audit records for externally settled payments."""
import sqlalchemy as sa
from alembic import op
revision='fin3111'
down_revision='fin3110'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('finance_settlement_reversals',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('payment_type',sa.String(24),nullable=False),
        sa.Column('payment_record_id',sa.Integer,nullable=False),
        sa.Column('original_amount',sa.Numeric(20,2),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('reason',sa.Text,nullable=False),
        sa.Column('evidence_reference',sa.Text,nullable=False),
        sa.Column('reversed_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('reversed_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('project_id','payment_type','payment_record_id',name='uq_finance_payment_reversed_once'))
    op.create_index('ix_finance_settlement_reversals_project_id','finance_settlement_reversals',['project_id'])

def downgrade():
    op.drop_table('finance_settlement_reversals')
