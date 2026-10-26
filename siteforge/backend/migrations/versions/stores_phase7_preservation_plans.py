"""Stores Phase 7 preservation plans and append-only check evidence."""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase7_preservation'
down_revision = 'stores_phase6_transfer_return_allocation'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('stores_preservation_plans',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('receipt_lot_id',sa.Integer(),sa.ForeignKey('stores_receipt_lots.id'),nullable=False),
        sa.Column('instructions',sa.Text(),nullable=False),
        sa.Column('frequency_days',sa.Integer(),nullable=False),
        sa.Column('next_due_date',sa.Date(),nullable=False),
        sa.Column('responsible_user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('last_checked_at',sa.DateTime(timezone=True)),
        sa.Column('condition',sa.String(20),nullable=False,server_default='Unverified'),
        sa.Column('version',sa.Integer(),nullable=False,server_default='1'),
        sa.Column('created_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('project_id','receipt_lot_id',name='uq_stores_preservation_project_lot'),
        sa.CheckConstraint('frequency_days > 0',name='ck_stores_preservation_frequency'))
    op.create_index('ix_stores_preservation_org_project','stores_preservation_plans',['organization_id','project_id'])
    op.create_table('stores_preservation_checks',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('plan_id',sa.Integer(),sa.ForeignKey('stores_preservation_plans.id'),nullable=False),
        sa.Column('request_key',sa.String(120),nullable=False),
        sa.Column('condition',sa.String(20),nullable=False),
        sa.Column('findings',sa.Text(),nullable=False),
        sa.Column('evidence',sa.Text(),nullable=False),
        sa.Column('checked_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('checked_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('plan_id','request_key',name='uq_stores_preservation_check_retry'))

def downgrade():
    op.drop_table('stores_preservation_checks')
    op.drop_index('ix_stores_preservation_org_project',table_name='stores_preservation_plans')
    op.drop_table('stores_preservation_plans')
