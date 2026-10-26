"""Phase 5 independent QA material usage evidence. No stock ledger mutation."""
from alembic import op
import sqlalchemy as sa
revision = 'a5f15015c001'
down_revision = 'stores_phase5_return_bin_placement'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('stores_construction_material_usages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('handover_id', sa.Integer(), sa.ForeignKey('stores_material_handovers.id'), nullable=False),
        sa.Column('work_package_id', sa.Integer(), sa.ForeignKey('work_packages.id'), nullable=False),
        sa.Column('item_id', sa.Integer(), sa.ForeignKey('procurement_items.id'), nullable=False),
        sa.Column('unit', sa.String(20), nullable=False),
        sa.Column('quantity', sa.Numeric(14,3), nullable=False),
        sa.Column('usage_type', sa.String(20), nullable=False),
        sa.Column('evidence_key', sa.String(120), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='Pending QA'),
        sa.Column('submitted_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('verified_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('verification_note', sa.Text(), nullable=False, server_default=''),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('project_id', 'evidence_key', name='uq_stores_usage_project_key'))
    for name in ('organization_id','project_id','handover_id','work_package_id'):
        op.create_index('ix_stores_construction_material_usages_' + name, 'stores_construction_material_usages', [name])

def downgrade():
    op.drop_table('stores_construction_material_usages')
