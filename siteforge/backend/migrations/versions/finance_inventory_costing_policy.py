"""Finance-owned inventory costing policy; no stock or journal posting.

Revision ID: finance_inventory_costing_policy
Revises: procurement_requirement_line_wbs
"""
from alembic import op
import sqlalchemy as sa
revision='finance_inventory_costing_policy'
down_revision='procurement_requirement_line_wbs'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('finance_inventory_costing_policies',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('costing_method',sa.String(32),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('effective_note',sa.Text(),nullable=False),
        sa.Column('status',sa.String(24),nullable=False),
        sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('submitted_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=True),
        sa.Column('approved_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=True),
        sa.Column('approved_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('decision_reason',sa.Text(),nullable=False),
        sa.UniqueConstraint('project_id','revision',name='uq_finance_inventory_policy_project_revision'))
    op.create_index('ix_finance_inventory_policy_scope','finance_inventory_costing_policies',['organization_id','project_id'])

def downgrade():
    op.drop_index('ix_finance_inventory_policy_scope',table_name='finance_inventory_costing_policies')
    op.drop_table('finance_inventory_costing_policies')
