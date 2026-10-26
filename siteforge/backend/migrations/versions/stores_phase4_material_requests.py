"""Stores Phase 4: approved material demand requests; no stock movements."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase4_material_requests'
down_revision = 'stores_phase3_work_scope_reassignment'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('stores_material_requests',
      sa.Column('id',sa.Integer(),primary_key=True),
      sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),
      sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
      sa.Column('request_key',sa.String(120),nullable=False),
      sa.Column('work_package_id',sa.Integer(),sa.ForeignKey('work_packages.id')),
      sa.Column('planning_wbs_id',sa.Integer(),sa.ForeignKey('planning_wbs.id')),
      sa.Column('item_id',sa.Integer(),sa.ForeignKey('procurement_items.id'),nullable=False),
      sa.Column('requested_quantity',sa.Numeric(14,3),nullable=False),
      sa.Column('base_unit',sa.String(20),nullable=False),
      sa.Column('required_date',sa.Date(),nullable=False),
      sa.Column('reason',sa.Text(),nullable=False,server_default=''),
      sa.Column('status',sa.String(24),nullable=False,server_default='Draft'),
      sa.Column('version',sa.Integer(),nullable=False,server_default='1'),
      sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
      sa.Column('reviewed_by',sa.Integer(),sa.ForeignKey('users.id')),
      sa.Column('review_reason',sa.Text(),nullable=False,server_default=''),
      sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
      sa.UniqueConstraint('project_id','request_key',name='uq_stores_material_request_key'))
    op.create_index('ix_stores_material_requests_project_id','stores_material_requests',['project_id'])
    op.create_index('ix_stores_material_requests_organization_id','stores_material_requests',['organization_id'])

def downgrade():
    op.drop_index('ix_stores_material_requests_organization_id',table_name='stores_material_requests')
    op.drop_index('ix_stores_material_requests_project_id',table_name='stores_material_requests')
    op.drop_table('stores_material_requests')
