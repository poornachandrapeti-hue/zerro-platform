"""Optional planning WBS on procurement requirement lines."""
from alembic import op
import sqlalchemy as sa
revision = 'procurement_requirement_line_wbs'
down_revision = 'stores_phase8_contract_obligation_link'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('material_requirement_lines', sa.Column('planning_wbs_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_material_requirement_lines_planning_wbs', 'material_requirement_lines',
                          'planning_wbs', ['planning_wbs_id'], ['id'])
    op.create_index('ix_material_requirement_lines_planning_wbs_id', 'material_requirement_lines', ['planning_wbs_id'])


def downgrade():
    op.drop_index('ix_material_requirement_lines_planning_wbs_id', table_name='material_requirement_lines')
    op.drop_constraint('fk_material_requirement_lines_planning_wbs', 'material_requirement_lines', type_='foreignkey')
    op.drop_column('material_requirement_lines', 'planning_wbs_id')
