"""Equipment E4 maintenance work orders with append-only transition evidence."""
from alembic import op
import sqlalchemy as sa
revision='equipment_e4_maintenance'
down_revision='equipment_e3_custody_movements'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('planning_equipment_maintenance_orders',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('asset_id',sa.Integer(),sa.ForeignKey('planning_equipment_assets.id'),nullable=False),
        sa.Column('request_key',sa.String(100),nullable=False),
        sa.Column('kind',sa.String(20),nullable=False),
        sa.Column('status',sa.String(24),nullable=False),
        sa.Column('title',sa.String(200),nullable=False),
        sa.Column('reported_reason',sa.Text(),nullable=False),
        sa.Column('due_on',sa.Date()),
        sa.Column('created_by',sa.Integer(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('repair_completed_by',sa.Integer()),
        sa.Column('repair_evidence_ref',sa.String(240)),
        sa.Column('released_by',sa.Integer()),
        sa.Column('released_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('organization_id','request_key',name='uq_equipment_maintenance_request'),
        sa.CheckConstraint("kind IN ('Preventive','Breakdown')",name='ck_equipment_maintenance_kind'),
        sa.CheckConstraint("status IN ('Reported','InRepair','RepairComplete','Released')",name='ck_equipment_maintenance_status'))
    op.create_table('planning_equipment_maintenance_events',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),nullable=False),
        sa.Column('order_id',sa.Integer(),sa.ForeignKey('planning_equipment_maintenance_orders.id'),nullable=False),
        sa.Column('old_status',sa.String(24)),
        sa.Column('new_status',sa.String(24),nullable=False),
        sa.Column('evidence_ref',sa.String(240),nullable=False),
        sa.Column('actor_id',sa.Integer(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    for table,fields in [('planning_equipment_maintenance_orders',['organization_id','project_id','asset_id']),
                         ('planning_equipment_maintenance_events',['organization_id','order_id'])]:
        for field in fields:op.create_index(f'ix_{table}_{field}',table,[field])

def downgrade():
    for table,fields in [('planning_equipment_maintenance_events',['organization_id','order_id']),
                         ('planning_equipment_maintenance_orders',['organization_id','project_id','asset_id'])]:
        for field in fields:op.drop_index(f'ix_{table}_{field}',table_name=table)
    op.drop_table('planning_equipment_maintenance_events')
    op.drop_table('planning_equipment_maintenance_orders')
