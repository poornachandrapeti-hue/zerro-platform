"""Phase 23 equipment identity and inspection evidence register."""
from alembic import op
import sqlalchemy as sa
revision='d3a23b92023'
down_revision='c2a8f4b92022'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('planning_equipment_assets',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),nullable=False),
        sa.Column('asset_code',sa.String(100),nullable=False),
        sa.Column('name',sa.String(200),nullable=False),
        sa.Column('equipment_type',sa.String(100),nullable=False),
        sa.Column('status',sa.String(30),nullable=False,server_default='Active'),
        sa.Column('inspection_valid_through',sa.Date(),nullable=True),
        sa.Column('inspection_evidence_ref',sa.String(240),nullable=True),
        sa.Column('created_by',sa.Integer(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('organization_id','asset_code',name='uq_planning_equipment_asset_code'))
    op.create_index('ix_planning_equipment_assets_organization_id','planning_equipment_assets',['organization_id'])
def downgrade():
    op.drop_index('ix_planning_equipment_assets_organization_id',table_name='planning_equipment_assets')
    op.drop_table('planning_equipment_assets')
