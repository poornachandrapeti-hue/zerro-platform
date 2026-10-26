"""Frozen per-policy PO line allocations."""
from alembic import op
import sqlalchemy as sa
revision='p10a1c4e7f724'
down_revision='p9a1c4e7f723'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('progress_milestone_policies',sa.Column('line_allocations',sa.JSON(),nullable=True))
def downgrade():
    op.drop_column('progress_milestone_policies','line_allocations')
