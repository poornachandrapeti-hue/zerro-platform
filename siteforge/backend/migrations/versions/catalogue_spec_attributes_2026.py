"""Add structured specifications to the existing catalogue; do not touch existing items.

Revision ID: catalogue_specs_26
Revises: eng_drawing_soft_delete
"""
from alembic import op
import sqlalchemy as sa

revision = "catalogue_specs_26"
down_revision = "eng_drawing_soft_delete"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("procurement_items", sa.Column("specification_attributes", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))

def downgrade():
    op.drop_column("procurement_items", "specification_attributes")
