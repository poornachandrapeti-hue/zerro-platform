"""Add optional contractual due date for certified client claims.

Revision ID: fin3114
Revises: fin3113
"""
from alembic import op
import sqlalchemy as sa
revision='fin3114'
down_revision='fin3113'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('finance_client_claims',sa.Column('due_date',sa.DateTime(timezone=True),nullable=True))

def downgrade():
    op.drop_column('finance_client_claims','due_date')
