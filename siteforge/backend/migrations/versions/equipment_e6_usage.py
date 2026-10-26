"""E6 equipment usage evidence without duplicate stock or progress ledgers."""
from alembic import op
import sqlalchemy as sa
revision='equipment_e6_usage'
down_revision='equipment_e5_compliance'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('planning_equipment_usage_records',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,nullable=False),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('asset_id',sa.Integer,sa.ForeignKey('planning_equipment_assets.id'),nullable=False),
        sa.Column('allocation_id',sa.Integer,sa.ForeignKey('planning_resource_allocations.id'),nullable=False),
        sa.Column('request_key',sa.String(100),nullable=False),
        sa.Column('starts_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('ends_at',sa.DateTime(timezone=True),nullable=False),
        *[sa.Column(k,sa.Numeric(12,3),nullable=False) for k in ('operating_hours','idle_hours','breakdown_hours','maintenance_hours')],
        sa.Column('meter_start',sa.Numeric(16,3)),sa.Column('meter_end',sa.Numeric(16,3)),
        sa.Column('fuel_liters',sa.Numeric(16,3)),sa.Column('anomaly_note',sa.Text),
        sa.Column('evidence_ref',sa.String(240),nullable=False),
        sa.Column('recorded_by',sa.Integer,nullable=False),
        sa.Column('recorded_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('organization_id','request_key',name='uq_equipment_usage_request_key'),
        sa.CheckConstraint('ends_at > starts_at',name='ck_equipment_usage_interval'),
        *[sa.CheckConstraint(f'{k} >= 0',name=f'ck_equipment_usage_{k}') for k in ('operating_hours','idle_hours','breakdown_hours','maintenance_hours')])
    op.create_index('ix_equipment_usage_org_asset_window','planning_equipment_usage_records',
        ['organization_id','asset_id','starts_at'])
    op.create_index('ix_equipment_usage_project','planning_equipment_usage_records',['project_id'])

def downgrade():
    op.drop_index('ix_equipment_usage_project',table_name='planning_equipment_usage_records')
    op.drop_index('ix_equipment_usage_org_asset_window',table_name='planning_equipment_usage_records')
    op.drop_table('planning_equipment_usage_records')
