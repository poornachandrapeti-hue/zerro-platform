"""Ordered, version-bound contract review hierarchy.
Revision ID: cm0103
Revises: cm0102
"""
from alembic import op
import sqlalchemy as sa
revision='cm0103'
down_revision='cm0102'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('contract_review_stages',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('contract_id',sa.Integer(),sa.ForeignKey('contract_register.id'),nullable=False),
        sa.Column('version_id',sa.Integer(),sa.ForeignKey('contract_versions.id'),nullable=False),
        sa.Column('step_no',sa.Integer(),nullable=False),
        sa.Column('label',sa.String(120),nullable=False),
        sa.Column('reviewer_user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('status',sa.String(30),nullable=False),
        sa.Column('decision_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=True),
        sa.Column('decided_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('decision_reason',sa.Text(),nullable=True),
        sa.UniqueConstraint('version_id','step_no'))
    op.create_index('ix_contract_review_stages_contract_id','contract_review_stages',['contract_id'])
    op.create_index('ix_contract_review_stages_version_id','contract_review_stages',['version_id'])

def downgrade():
    op.drop_index('ix_contract_review_stages_version_id',table_name='contract_review_stages')
    op.drop_index('ix_contract_review_stages_contract_id',table_name='contract_review_stages')
    op.drop_table('contract_review_stages')
