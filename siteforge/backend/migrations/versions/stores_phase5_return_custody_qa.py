"""Phase 5 return custody and QA disposition (non-ledger)."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase5_return_custody_qa'
down_revision = 'stores_phase5_discrepancy_resolution'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('stores_material_returns',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('handover_id', sa.Integer(), sa.ForeignKey('stores_material_handovers.id'), nullable=False),
        sa.Column('requested_quantity', sa.Numeric(14, 3), nullable=False),
        sa.Column('condition', sa.String(24), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('submitted_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('received_quantity', sa.Numeric(14,3)),
        sa.Column('receipt_evidence', sa.Text(), nullable=False),
        sa.Column('received_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('qa_decision', sa.String(24)),
        sa.Column('qa_evidence', sa.Text(), nullable=False),
        sa.Column('qa_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('handover_id', name='uq_stores_return_handover'))
    op.create_index('ix_stores_returns_org_project', 'stores_material_returns', ['organization_id','project_id'])

def downgrade():
    op.drop_index('ix_stores_returns_org_project', table_name='stores_material_returns')
    op.drop_table('stores_material_returns')
