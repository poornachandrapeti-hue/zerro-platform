"""Audited milestone achievement evidence."""
from alembic import op
import sqlalchemy as sa
revision='o2f6a8b0c315'
down_revision='n1c5d7e9f203'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('planning_milestone_evidence',
      sa.Column('id',sa.Integer(),primary_key=True),
      sa.Column('organization_id',sa.Integer(),nullable=False),
      sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
      sa.Column('publication_id',sa.Integer(),sa.ForeignKey('planning_publications.id'),nullable=False),
      sa.Column('activity_code',sa.String(80),nullable=False),
      sa.Column('achieved_on',sa.Date(),nullable=False),
      sa.Column('evidence_ref',sa.String(240),nullable=False),
      sa.Column('submitted_by',sa.Integer(),nullable=False),
      sa.Column('submitted_at',sa.DateTime(timezone=True),nullable=False),
      sa.Column('status',sa.String(24),nullable=False),
      sa.Column('reviewed_by',sa.Integer()),
      sa.Column('reviewed_at',sa.DateTime(timezone=True)),
      sa.Column('review_note',sa.Text(),nullable=False),
      sa.UniqueConstraint('publication_id','activity_code',name='uq_planning_milestone_evidence'))
    op.create_index('ix_milestone_evidence_org_project','planning_milestone_evidence',['organization_id','project_id'])
def downgrade():
    op.drop_index('ix_milestone_evidence_org_project',table_name='planning_milestone_evidence')
    op.drop_table('planning_milestone_evidence')
