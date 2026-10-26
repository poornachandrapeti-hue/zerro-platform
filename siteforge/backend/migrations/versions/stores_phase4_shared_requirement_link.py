"""Link Stores issue requests to authoritative Procurement requirement lines.

Legacy standalone requests must be remediated to an approved line before submission/approval.
"""
from alembic import op
import sqlalchemy as sa
revision = 'stores_phase4_shared_requirement_link'
down_revision = 'stores_phase4_material_requests'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('stores_material_requests', sa.Column('requirement_line_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_stores_request_requirement_line', 'stores_material_requests', 'material_requirement_lines', ['requirement_line_id'], ['id'])
    op.create_index('ix_stores_material_requests_requirement_line_id', 'stores_material_requests', ['requirement_line_id'])

def downgrade():
    op.drop_index('ix_stores_material_requests_requirement_line_id', table_name='stores_material_requests')
    op.drop_constraint('fk_stores_request_requirement_line', 'stores_material_requests', type_='foreignkey')
    op.drop_column('stores_material_requests', 'requirement_line_id')
