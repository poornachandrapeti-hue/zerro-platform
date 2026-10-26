"""Phase 24: equipment inspection review and audit history."""
from alembic import op
import sqlalchemy as sa
revision='e4b24c92024'
down_revision='d3a23b92023'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('planning_equipment_assets',sa.Column('inspection_review_status',sa.String(20),nullable=False,server_default='Pending'))
    op.add_column('planning_equipment_assets',sa.Column('inspection_reviewed_by',sa.Integer(),nullable=True))
    op.add_column('planning_equipment_assets',sa.Column('inspection_reviewed_at',sa.DateTime(timezone=True),nullable=True))
    op.create_table('planning_equipment_inspection_decisions',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),nullable=False),
        sa.Column('asset_id',sa.Integer(),sa.ForeignKey('planning_equipment_assets.id'),nullable=False),
        sa.Column('reviewer_id',sa.Integer(),nullable=False),
        sa.Column('decision',sa.String(20),nullable=False),
        sa.Column('note',sa.Text(),nullable=False),
        sa.Column('evidence_ref',sa.String(240),nullable=False),
        sa.Column('valid_through',sa.Date(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index('ix_planning_equipment_inspection_decisions_asset_id','planning_equipment_inspection_decisions',['asset_id'])
    op.create_index('ix_planning_equipment_inspection_decisions_organization_id','planning_equipment_inspection_decisions',['organization_id'])
def downgrade():
    op.drop_index('ix_planning_equipment_inspection_decisions_organization_id',table_name='planning_equipment_inspection_decisions')
    op.drop_index('ix_planning_equipment_inspection_decisions_asset_id',table_name='planning_equipment_inspection_decisions')
    op.drop_table('planning_equipment_inspection_decisions')
    op.drop_column('planning_equipment_assets','inspection_reviewed_at')
    op.drop_column('planning_equipment_assets','inspection_reviewed_by')
    op.drop_column('planning_equipment_assets','inspection_review_status')
