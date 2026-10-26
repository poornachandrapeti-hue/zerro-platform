"""Append-only equipment custody journal, separate from Stores stock."""
from alembic import op
import sqlalchemy as sa
revision='equipment_e3_custody_movements'
down_revision='equipment_e2_asset_metadata'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('planning_equipment_custody_movements',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('asset_id',sa.Integer(),sa.ForeignKey('planning_equipment_assets.id'),nullable=False),
        sa.Column('allocation_id',sa.Integer(),sa.ForeignKey('planning_resource_allocations.id')),
        sa.Column('parent_issue_id',sa.Integer(),sa.ForeignKey('planning_equipment_custody_movements.id')),
        sa.Column('action',sa.String(20),nullable=False),
        sa.Column('quantity',sa.Integer(),nullable=False),
        sa.Column('custodian_user_id',sa.Integer(),nullable=False),
        sa.Column('location',sa.String(200),nullable=False),
        sa.Column('reason',sa.Text(),nullable=False),
        sa.Column('evidence_ref',sa.String(240),nullable=False),
        sa.Column('request_key',sa.String(100),nullable=False),
        sa.Column('recorded_by',sa.Integer(),nullable=False),
        sa.Column('recorded_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('organization_id','request_key',name='uq_equipment_custody_request'),
        sa.CheckConstraint('quantity > 0',name='ck_equipment_custody_qty'),
        sa.CheckConstraint("action IN ('Issue','Return')",name='ck_equipment_custody_action'),
        sa.CheckConstraint("(action='Issue' AND parent_issue_id IS NULL) OR (action='Return' AND parent_issue_id IS NOT NULL)",name='ck_equipment_custody_parent'))
    for field in ['organization_id','project_id','asset_id']:
        op.create_index(f'ix_equipment_custody_{field}','planning_equipment_custody_movements',[field])

def downgrade():
    for field in ['organization_id','project_id','asset_id']:
        op.drop_index(f'ix_equipment_custody_{field}',table_name='planning_equipment_custody_movements')
    op.drop_table('planning_equipment_custody_movements')
