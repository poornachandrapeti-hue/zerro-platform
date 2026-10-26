"""Isolated partner Planning commitment audit register."""
from alembic import op
import sqlalchemy as sa
revision = 'f5c392e28a47'
down_revision = 'e4b24c92024'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('planning_partner_commitments',
      sa.Column('id',sa.Integer(),primary_key=True),
      sa.Column('organization_id',sa.Integer(),nullable=False),
      sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
      sa.Column('schedule_id',sa.Integer(),sa.ForeignKey('planning_schedules.id'),nullable=False),
      sa.Column('activity_id',sa.Integer(),sa.ForeignKey('planning_activities.id'),nullable=False),
      sa.Column('company_id',sa.Integer(),nullable=False),
      sa.Column('submitted_by',sa.Integer(),nullable=False),
      sa.Column('submitted_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
      sa.Column('commitment',sa.String(20),nullable=False),
      sa.Column('expected_date',sa.Date(),nullable=True),
      sa.Column('note',sa.Text(),nullable=False,server_default=''),
      sa.Column('status',sa.String(20),nullable=False,server_default='Submitted'),
      sa.Column('reviewed_by',sa.Integer(),nullable=True),
      sa.Column('reviewed_at',sa.DateTime(timezone=True),nullable=True),
      sa.Column('review_note',sa.Text(),nullable=False,server_default=''))
    op.create_index('ix_partner_commitment_project','planning_partner_commitments',['project_id'])
    op.create_index('ix_partner_commitment_org','planning_partner_commitments',['organization_id'])
    op.create_index('ix_partner_commitment_company','planning_partner_commitments',['company_id'])

def downgrade():
    op.drop_index('ix_partner_commitment_company',table_name='planning_partner_commitments')
    op.drop_index('ix_partner_commitment_org',table_name='planning_partner_commitments')
    op.drop_index('ix_partner_commitment_project',table_name='planning_partner_commitments')
    op.drop_table('planning_partner_commitments')
