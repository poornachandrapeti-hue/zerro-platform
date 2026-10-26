"""Append-only approval authority and decision evidence (phase 31.11)."""
import sqlalchemy as sa
from alembic import op
revision='fin3110'
down_revision='fin3109'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('finance_authority_audit',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('authority_id',sa.Integer,sa.ForeignKey('finance_payment_approval_limits.id'),nullable=False),
        sa.Column('target_user_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('changed_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('payment_type',sa.String(24),nullable=False),
        sa.Column('previous_amount',sa.Numeric(20,2),nullable=True),
        sa.Column('new_amount',sa.Numeric(20,2),nullable=False),
        sa.Column('previous_active',sa.Boolean,nullable=True),
        sa.Column('new_active',sa.Boolean,nullable=False),
        sa.Column('reason',sa.Text,nullable=False),
        sa.Column('changed_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_finance_authority_audit_project_id','finance_authority_audit',['project_id'])
    op.create_index('ix_finance_authority_audit_authority_id','finance_authority_audit',['authority_id'])
    op.create_table('finance_payment_decision_audit',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('payment_type',sa.String(24),nullable=False),
        sa.Column('request_id',sa.Integer,nullable=False),
        sa.Column('decision',sa.String(24),nullable=False),
        sa.Column('actor_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('request_amount',sa.Numeric(20,2),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('authority_mode',sa.String(40),nullable=False),
        sa.Column('reason',sa.Text,nullable=False),
        sa.Column('decided_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_finance_payment_decision_audit_project_id','finance_payment_decision_audit',['project_id'])

def downgrade():
    op.drop_table('finance_payment_decision_audit')
    op.drop_table('finance_authority_audit')
