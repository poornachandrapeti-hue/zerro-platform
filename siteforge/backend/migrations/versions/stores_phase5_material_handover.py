"""Material dispatch and contractor receipt evidence; no inventory movement."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase5_material_handover'
down_revision = 'stores_phase4_request_permissions'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('stores_material_handovers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('stock_posting_line_id', sa.Integer(), sa.ForeignKey('stock_posting_lines.id'), nullable=False),
        sa.Column('material_request_id', sa.Integer(), sa.ForeignKey('stores_material_requests.id'), nullable=False),
        sa.Column('dispatched_quantity', sa.Numeric(14,3), nullable=False),
        sa.Column('received_quantity', sa.Numeric(14,3)),
        sa.Column('damaged_quantity', sa.Numeric(14,3)),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('handover_reference', sa.String(120), nullable=False),
        sa.Column('dispatch_evidence', sa.Text(), nullable=False),
        sa.Column('discrepancy_note', sa.Text(), nullable=False),
        sa.Column('acknowledgment_evidence', sa.Text(), nullable=False),
        sa.Column('dispatched_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('acknowledged_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('stock_posting_line_id', name='uq_stores_handover_issue_line'))
    op.create_index('ix_stores_handover_org_project', 'stores_material_handovers', ['organization_id','project_id'])

def downgrade():
    op.drop_index('ix_stores_handover_org_project', 'stores_material_handovers')
    op.drop_table('stores_material_handovers')
