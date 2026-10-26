"""Extend the canonical Planning equipment asset register for E2 master lifecycle."""
from alembic import op
import sqlalchemy as sa
revision='equipment_e2_asset_metadata'
down_revision='finance_movement_journal_proposals'
branch_labels=None
depends_on=None

def upgrade():
    table='planning_equipment_assets'
    for col in (
        sa.Column('make',sa.String(120)), sa.Column('model',sa.String(120)),
        sa.Column('serial_number',sa.String(160)), sa.Column('owner_company',sa.String(200)),
        sa.Column('ownership_type',sa.String(24),nullable=False,server_default='Owned'),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id')),
        sa.Column('location',sa.String(200)), sa.Column('custodian_user_id',sa.Integer()),
        sa.Column('operating_condition',sa.String(24),nullable=False,server_default='Unknown'),
        sa.Column('capacity',sa.String(160)), sa.Column('operating_specs',sa.JSON()),
        sa.Column('mobilized_on',sa.Date()), sa.Column('demobilized_on',sa.Date()),
        sa.Column('hire_contract_ref',sa.String(160)), sa.Column('maintenance_requirements',sa.Text()),
        sa.Column('tracking_mode',sa.String(24),nullable=False,server_default='Individual'),
        sa.Column('quantity',sa.Integer(),nullable=False,server_default='1'),
    ):op.add_column(table,col)
    op.create_index('ix_planning_equipment_assets_project_id',table,['project_id'])
    op.create_check_constraint('ck_equipment_e2_quantity_positive',table,'quantity >= 1')
    op.create_check_constraint('ck_equipment_e2_tracking',table,"tracking_mode IN ('Individual','QuantityManaged')")
    op.create_check_constraint('ck_equipment_e2_ownership',table,"ownership_type IN ('Owned','Hired','Subcontractor')")
    op.create_check_constraint('ck_equipment_e2_dates',table,'demobilized_on IS NULL OR (mobilized_on IS NOT NULL AND demobilized_on >= mobilized_on)')
    op.create_table('planning_equipment_master_changes',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),nullable=False),
        sa.Column('asset_id',sa.Integer(),sa.ForeignKey('planning_equipment_assets.id'),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('changed_by',sa.Integer(),nullable=False),
        sa.Column('changed_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('action',sa.String(30),nullable=False), sa.Column('reason',sa.Text(),nullable=False),
        sa.Column('before_state',sa.JSON(),nullable=False),sa.Column('after_state',sa.JSON(),nullable=False))
    op.create_index('ix_planning_equipment_master_changes_asset_id','planning_equipment_master_changes',['asset_id'])
    op.create_index('ix_planning_equipment_master_changes_organization_id','planning_equipment_master_changes',['organization_id'])

def downgrade():
    op.drop_index('ix_planning_equipment_master_changes_organization_id',table_name='planning_equipment_master_changes')
    op.drop_index('ix_planning_equipment_master_changes_asset_id',table_name='planning_equipment_master_changes')
    op.drop_table('planning_equipment_master_changes')
    table='planning_equipment_assets'
    for c in ['ck_equipment_e2_dates','ck_equipment_e2_ownership','ck_equipment_e2_tracking','ck_equipment_e2_quantity_positive']:
        op.drop_constraint(c,table,type_='check')
    op.drop_index('ix_planning_equipment_assets_project_id',table_name=table)
    for name in ['quantity','tracking_mode','maintenance_requirements','hire_contract_ref',
                 'demobilized_on','mobilized_on','operating_specs','capacity',
                 'operating_condition','custodian_user_id','location','project_id',
                 'ownership_type','owner_company','serial_number','model','make']:
        op.drop_column(table,name)
