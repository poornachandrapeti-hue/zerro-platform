"""Finance-owned PO cost coding and supplier invoice posting metadata."""
import sqlalchemy as sa
from alembic import op
revision='fin3102'
down_revision='fin3101'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('finance_procurement_allocations',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('purchase_order_id',sa.Integer,sa.ForeignKey('purchase_orders.id'),nullable=False),
        sa.Column('cost_code_id',sa.Integer,sa.ForeignKey('finance_cost_codes.id'),nullable=False),
        sa.Column('assigned_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('assigned_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('project_id','purchase_order_id'))
    op.create_table('finance_supplier_invoice_postings',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('vendor_invoice_id',sa.Integer,sa.ForeignKey('vendor_invoices.id'),nullable=False),
        sa.Column('purchase_order_id',sa.Integer,sa.ForeignKey('purchase_orders.id'),nullable=False),
        sa.Column('cost_code_id',sa.Integer,sa.ForeignKey('finance_cost_codes.id'),nullable=False),
        sa.Column('currency',sa.String(8),nullable=False),
        sa.Column('amount',sa.Numeric(20,2),nullable=False),
        sa.Column('posted_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('posted_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('verification_note',sa.Text,nullable=False),
        sa.UniqueConstraint('project_id','vendor_invoice_id'))
    for table in ('finance_procurement_allocations','finance_supplier_invoice_postings'):
        op.create_index('ix_'+table+'_project_id',table,['project_id'])
        op.create_index('ix_'+table+'_organization_id',table,['organization_id'])

def downgrade():
    op.drop_table('finance_supplier_invoice_postings')
    op.drop_table('finance_procurement_allocations')
