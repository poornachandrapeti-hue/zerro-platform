"""Phase 7 scrap case custody evidence. No inventory write-off."""
from alembic import op
import sqlalchemy as sa
revision='stores_phase7_scrap_disposal'
down_revision='stores_phase7_adjustment_requests'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('stores_scrap_cases',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('reference',sa.String(120),nullable=False),
        sa.Column('receipt_lot_id',sa.Integer(),sa.ForeignKey('stores_receipt_lots.id'),nullable=False),
        sa.Column('quantity',sa.Numeric(14,3),nullable=False),
        sa.Column('classification',sa.String(30),nullable=False),
        sa.Column('reason',sa.Text(),nullable=False),
        sa.Column('evidence',sa.Text(),nullable=False),
        sa.Column('status',sa.String(32),nullable=False,server_default='Proposed'),
        sa.Column('version',sa.Integer(),nullable=False,server_default='1'),
        sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('reviewed_by',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('review_evidence',sa.Text(),nullable=False,server_default=''),
        sa.Column('disposal_reference',sa.String(120),nullable=False,server_default=''),
        sa.Column('disposal_evidence',sa.Text(),nullable=False,server_default=''),
        sa.Column('disposal_recorded_by',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('project_id','reference',name='uq_stores_scrap_project_reference'))
    op.create_index('ix_stores_scrap_org_project','stores_scrap_cases',['organization_id','project_id'])
    op.create_index('ix_stores_scrap_receipt_lot','stores_scrap_cases',['receipt_lot_id'])

def downgrade():
    op.drop_index('ix_stores_scrap_receipt_lot',table_name='stores_scrap_cases')
    op.drop_index('ix_stores_scrap_org_project',table_name='stores_scrap_cases')
    op.drop_table('stores_scrap_cases')
