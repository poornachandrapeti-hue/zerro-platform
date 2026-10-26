"""widen review decision action for approve_with_comments"""

from alembic import op
import sqlalchemy as sa


revision = "e5c2a9b81d04"
down_revision = "d8a1c6e54f30"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "review_decisions",
        "action",
        existing_type=sa.String(length=20),
        type_=sa.String(length=40),
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        "review_decisions",
        "action",
        existing_type=sa.String(length=40),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
