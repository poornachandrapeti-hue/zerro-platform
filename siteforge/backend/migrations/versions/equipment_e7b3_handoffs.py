"""E7B3 traceable evidence receipts; no accounting or inventory postings."""
from alembic import op
import sqlalchemy as sa
revision = 'equipment_e7b3_handoffs'
down_revision = 'equipment_e6_usage'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('planning_equipment_authority_handoffs',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('organization_id', sa.Integer, nullable=False),
        sa.Column('project_id', sa.Integer, sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('asset_id', sa.Integer, sa.ForeignKey('planning_equipment_assets.id'), nullable=False),
        sa.Column('authority_kind', sa.String(20), nullable=False),
        sa.Column('authority_id', sa.Integer, nullable=False),
        sa.Column('request_key', sa.String(100), nullable=False),
        sa.Column('evidence_ref', sa.String(240), nullable=False),
        sa.Column('authority_snapshot', sa.JSON, nullable=False),
        sa.Column('created_by', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint('organization_id', 'request_key',
                            name='uq_equipment_authority_handoff_key'),
        sa.CheckConstraint("authority_kind IN ('HireContract', 'StoresSpareRequest')",
                           name='ck_equipment_authority_handoff_kind'))
    for col in ('organization_id', 'project_id', 'asset_id'):
        op.create_index(f'ix_e7b3_handoff_{col}', 'planning_equipment_authority_handoffs', [col])


def downgrade():
    for col in ('asset_id', 'project_id', 'organization_id'):
        op.drop_index(f'ix_e7b3_handoff_{col}', table_name='planning_equipment_authority_handoffs')
    op.drop_table('planning_equipment_authority_handoffs')
