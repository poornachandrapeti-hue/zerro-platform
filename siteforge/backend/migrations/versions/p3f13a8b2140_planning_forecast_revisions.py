"""Planning forecast versions and independent approval."""
from alembic import op
import sqlalchemy as sa
revision = 'p3f13a8b2140'
down_revision = 'o2f6a8b0c315'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('planning_forecast_revisions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('schedule_id', sa.Integer(), sa.ForeignKey('planning_schedules.id'), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('data_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('inputs', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('submitted_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_by', sa.Integer()),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.Column('review_note', sa.Text(), nullable=False),
        sa.UniqueConstraint('schedule_id','revision',name='uq_planning_forecast_revision'))
    op.create_index('ix_planning_forecast_org_project','planning_forecast_revisions',['organization_id','project_id'])

def downgrade():
    op.drop_index('ix_planning_forecast_org_project', table_name='planning_forecast_revisions')
    op.drop_table('planning_forecast_revisions')
