"""Explicit approved-period targets and captured source progress."""
from alembic import op
import sqlalchemy as sa
revision='j5e8c2d4f710'
down_revision='i3d5e7f9a021'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('planning_period_targets',
        sa.Column('id',sa.Integer,primary_key=True),sa.Column('organization_id',sa.Integer,nullable=False),
        sa.Column('project_id',sa.Integer,nullable=False),sa.Column('publication_id',sa.Integer,sa.ForeignKey('planning_publications.id'),nullable=False),
        sa.Column('activity_id',sa.Integer,nullable=False),sa.Column('period_end',sa.Date,nullable=False),
        sa.Column('cumulative_percent',sa.Integer,nullable=False),sa.Column('weight_basis_points',sa.Integer,nullable=False),
        sa.Column('created_by',sa.Integer,nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('publication_id','activity_id','period_end',name='uq_planning_period_target'))
    op.create_table('planning_progress_captures',
        sa.Column('id',sa.Integer,primary_key=True),sa.Column('organization_id',sa.Integer,nullable=False),
        sa.Column('project_id',sa.Integer,nullable=False),sa.Column('publication_id',sa.Integer,sa.ForeignKey('planning_publications.id'),nullable=False),
        sa.Column('captured_at',sa.DateTime(timezone=True),nullable=False),sa.Column('captured_by',sa.Integer,nullable=False),sa.Column('snapshot',sa.JSON,nullable=False))
    for table in ('planning_period_targets','planning_progress_captures'):
        for column in ('project_id','publication_id','organization_id'):
            op.create_index(f'ix_{table}_{column}',table,[column])

def downgrade():
    op.drop_table('planning_progress_captures')
    op.drop_table('planning_period_targets')
