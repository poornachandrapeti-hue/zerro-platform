"""Finance-owned journal proposals. No GL posting authority created."""
from alembic import op
import sqlalchemy as sa
revision='finance_movement_journal_proposals'
down_revision='finance_receipt_cost_allocations'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('finance_movement_journal_proposals',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('source_movement_line_id',sa.Integer(),sa.ForeignKey('stock_posting_lines.id'),nullable=False),
        sa.Column('proposal_revision',sa.Integer(),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('description',sa.String(400),nullable=False),
        sa.Column('lines',sa.JSON(),nullable=False),
        sa.Column('status',sa.String(24),nullable=False),
        sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('submitted_by',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('approved_by',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('approved_at',sa.DateTime(timezone=True)),
        sa.Column('decision_reason',sa.Text(),nullable=False),
        sa.UniqueConstraint('project_id','source_movement_line_id','proposal_revision',name='uq_finance_movement_proposal_revision'))
    op.create_index('ix_finance_journal_proposal_scope','finance_movement_journal_proposals',['organization_id','project_id'])

def downgrade():
    op.drop_index('ix_finance_journal_proposal_scope',table_name='finance_movement_journal_proposals')
    op.drop_table('finance_movement_journal_proposals')
