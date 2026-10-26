"""Phase 22 Planning allocation review metadata."""
from alembic import op
import sqlalchemy as sa
revision='c2a8f4b92022'
down_revision='b1f7e3a92021'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('planning_resource_allocations',sa.Column('reviewed_by',sa.Integer(),nullable=True))
    op.add_column('planning_resource_allocations',sa.Column('reviewed_at',sa.DateTime(timezone=True),nullable=True))
    op.add_column('planning_resource_allocations',sa.Column('review_note',sa.Text(),nullable=False,server_default=''))

def downgrade():
    op.drop_column('planning_resource_allocations','review_note')
    op.drop_column('planning_resource_allocations','reviewed_at')
    op.drop_column('planning_resource_allocations','reviewed_by')
