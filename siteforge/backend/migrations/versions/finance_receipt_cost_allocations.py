"""Finance receipt-line invoice-cost allocation (unposted evidence only)."""
from alembic import op
import sqlalchemy as sa
revision='finance_receipt_cost_allocations'
down_revision='finance_landed_cost_batches'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('finance_receipt_cost_allocations',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('goods_receipt_line_id',sa.Integer(),sa.ForeignKey('goods_receipt_lines.id'),nullable=False),
        sa.Column('vendor_invoice_line_id',sa.Integer(),sa.ForeignKey('vendor_invoice_lines.id'),nullable=False),
        sa.Column('quantity',sa.Numeric(20,6),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('unit_cost',sa.Numeric(20,6),nullable=False),
        sa.Column('source_reference',sa.String(160),nullable=False),
        sa.Column('status',sa.String(24),nullable=False),
        sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('submitted_by',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('approved_by',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('approved_at',sa.DateTime(timezone=True)),
        sa.Column('decision_reason',sa.Text(),nullable=False),
        sa.UniqueConstraint('project_id','goods_receipt_line_id','vendor_invoice_line_id',name='uq_finance_receipt_invoice_allocation'),
        sa.CheckConstraint('quantity > 0',name='ck_finance_receipt_quantity'),
        sa.CheckConstraint('unit_cost > 0',name='ck_finance_receipt_cost'))
    op.create_index('ix_finance_receipt_cost_scope','finance_receipt_cost_allocations',['organization_id','project_id'])

def downgrade():
    op.drop_index('ix_finance_receipt_cost_scope',table_name='finance_receipt_cost_allocations')
    op.drop_table('finance_receipt_cost_allocations')
