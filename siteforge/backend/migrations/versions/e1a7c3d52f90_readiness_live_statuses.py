"""Readiness: Not Applicable status and Material issue check type.

Revision ID: e1a7c3d52f90
Revises: d5f9c3a72e08
"""
from alembic import op

revision = "e1a7c3d52f90"
down_revision = "d5f9c3a72e08"
branch_labels = None
depends_on = None

TYPES = (
    "check_type IN ('Drawing', 'Material', 'Material issue', 'Predecessor', 'Workfront', 'Manpower', "
    "'Procedure', 'Inspection', 'Permit', 'Quality hold')"
)
STATUSES = "status IN ('Not Checked', 'Pending', 'Satisfied', 'Blocked', 'Not Applicable')"


def upgrade():
    op.drop_constraint("ck_construction_readiness_type", "construction_readiness", type_="check")
    op.create_check_constraint("ck_construction_readiness_type", "construction_readiness", TYPES)
    op.drop_constraint("ck_construction_readiness_status", "construction_readiness", type_="check")
    op.create_check_constraint("ck_construction_readiness_status", "construction_readiness", STATUSES)


def downgrade():
    # Rows may already use the new values.
    pass
