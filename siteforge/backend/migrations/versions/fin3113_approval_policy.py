"""Optional strict project payment authority policies with append-only change history."""
import sqlalchemy as sa
from alembic import op
revision='fin3113'
down_revision='fin3112'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('finance_approval_policies',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('payment_type',sa.String(24),nullable=False),
        sa.Column('require_configured_authority',sa.Boolean,nullable=False,server_default=sa.false()),
        sa.Column('overdue_after_hours',sa.Integer,nullable=False,server_default='48'),
        sa.Column('changed_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('changed_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('project_id','payment_type',name='uq_finance_approval_policy'))
    op.create_index('ix_finance_approval_policies_project_id','finance_approval_policies',['project_id'])
    op.create_table('finance_approval_policy_audit',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('payment_type',sa.String(24),nullable=False),
        sa.Column('actor_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('previous_policy',sa.JSON,nullable=True),
        sa.Column('new_policy',sa.JSON,nullable=False),
        sa.Column('reason',sa.Text,nullable=False),
        sa.Column('changed_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_finance_approval_policy_audit_project_id','finance_approval_policy_audit',['project_id'])

def downgrade():
    op.drop_index('ix_finance_approval_policy_audit_project_id',table_name='finance_approval_policy_audit')
    op.drop_table('finance_approval_policy_audit')
    op.drop_index('ix_finance_approval_policies_project_id',table_name='finance_approval_policies')
    op.drop_table('finance_approval_policies')
