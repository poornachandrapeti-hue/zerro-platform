"""Equipment E5 independent compliance reviews and safety holds."""
from alembic import op
import sqlalchemy as sa
revision='equipment_e5_compliance'
down_revision='equipment_e4_maintenance'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('planning_equipment_compliance_evidence',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,nullable=False),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('asset_id',sa.Integer,sa.ForeignKey('planning_equipment_assets.id'),nullable=False),
        sa.Column('request_key',sa.String(100),nullable=False),
        sa.Column('kind',sa.String(24),nullable=False),
        sa.Column('evidence_ref',sa.String(240),nullable=False),
        sa.Column('valid_through',sa.Date,nullable=False),
        sa.Column('required',sa.Boolean,nullable=False,server_default=sa.true()),
        sa.Column('status',sa.String(20),nullable=False),
        sa.Column('created_by',sa.Integer,nullable=False),
        sa.Column('reviewed_by',sa.Integer),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('reviewed_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('organization_id','request_key',name='uq_equipment_compliance_request'),
        sa.CheckConstraint("kind IN ('Calibration','Certification','Inspection')",name='ck_equipment_compliance_kind'),
        sa.CheckConstraint("status IN ('Pending','Verified','Rejected')",name='ck_equipment_compliance_status'))
    op.create_table('planning_equipment_safety_holds',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,nullable=False),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('asset_id',sa.Integer,sa.ForeignKey('planning_equipment_assets.id'),nullable=False),
        sa.Column('request_key',sa.String(100),nullable=False),
        sa.Column('reason',sa.Text,nullable=False),
        sa.Column('evidence_ref',sa.String(240),nullable=False),
        sa.Column('status',sa.String(20),nullable=False),
        sa.Column('created_by',sa.Integer,nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('released_by',sa.Integer),
        sa.Column('release_evidence_ref',sa.String(240)),
        sa.Column('released_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('organization_id','request_key',name='uq_equipment_safety_hold_request'),
        sa.CheckConstraint("status IN ('Active','Released')",name='ck_equipment_hold_status'))
    for table in ('planning_equipment_compliance_evidence','planning_equipment_safety_holds'):
        op.create_index('ix_'+table+'_org_asset',table,['organization_id','asset_id'])
        op.create_index('ix_'+table+'_project',table,['project_id'])

def downgrade():
    for table in ('planning_equipment_safety_holds','planning_equipment_compliance_evidence'):
        op.drop_index('ix_'+table+'_project',table_name=table)
        op.drop_index('ix_'+table+'_org_asset',table_name=table)
        op.drop_table(table)
