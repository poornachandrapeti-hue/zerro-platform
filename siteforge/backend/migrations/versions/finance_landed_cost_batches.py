"""Finance landed charge approvals and original receipt references only.

Revision ID: finance_landed_cost_batches
Revises: finance_inventory_costing_policy
"""
from alembic import op
import sqlalchemy as sa
revision='finance_landed_cost_batches'
down_revision='finance_inventory_costing_policy'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('finance_landed_cost_batches',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('document_ref',sa.String(100),nullable=False),
        sa.Column('category',sa.String(40),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('amount',sa.Numeric(20,2),nullable=False),
        sa.Column('source_document',sa.String(200),nullable=False),
        sa.Column('status',sa.String(24),nullable=False),
        sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('submitted_by',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('approved_by',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('approved_at',sa.DateTime(timezone=True)),
        sa.Column('decision_reason',sa.Text(),nullable=False),
        sa.UniqueConstraint('project_id','document_ref',name='uq_finance_landed_cost_document'),
        sa.CheckConstraint('amount > 0',name='ck_finance_landed_cost_positive'))
    op.create_index('ix_finance_landed_cost_scope','finance_landed_cost_batches',['organization_id','project_id'])
    op.create_table('finance_landed_cost_receipt_links',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('batch_id',sa.Integer(),sa.ForeignKey('finance_landed_cost_batches.id'),nullable=False),
        sa.Column('goods_receipt_line_id',sa.Integer(),sa.ForeignKey('goods_receipt_lines.id'),nullable=False),
        sa.UniqueConstraint('batch_id','goods_receipt_line_id',name='uq_finance_landed_batch_receipt'))
    op.create_index('ix_finance_landed_cost_receipt','finance_landed_cost_receipt_links',['goods_receipt_line_id'])

def downgrade():
    op.drop_index('ix_finance_landed_cost_receipt',table_name='finance_landed_cost_receipt_links')
    op.drop_table('finance_landed_cost_receipt_links')
    op.drop_index('ix_finance_landed_cost_scope',table_name='finance_landed_cost_batches')
    op.drop_table('finance_landed_cost_batches')
