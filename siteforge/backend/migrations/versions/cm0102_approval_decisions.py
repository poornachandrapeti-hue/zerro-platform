"""Version-bound contract approval evidence.

Revision ID: cm0102
Revises: cm0101
"""
from alembic import op
import sqlalchemy as sa
revision='cm0102'
down_revision='cm0101'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('contract_approval_decisions',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contract_register.id'),nullable=False),
        sa.Column('version_id',sa.Integer(),sa.ForeignKey('contract_versions.id'),nullable=False),
        sa.Column('actor_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('decision',sa.String(30),nullable=False),
        sa.Column('reason',sa.Text(),nullable=False),
        sa.Column('recorded_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('contract_id','version_id','decision'))
    op.create_index('ix_contract_approval_decisions_contract_id','contract_approval_decisions',['contract_id'])
    op.create_index('ix_contract_approval_decisions_version_id','contract_approval_decisions',['version_id'])

def downgrade():
    op.drop_index('ix_contract_approval_decisions_version_id',table_name='contract_approval_decisions')
    op.drop_index('ix_contract_approval_decisions_contract_id',table_name='contract_approval_decisions')
    op.drop_table('contract_approval_decisions')
