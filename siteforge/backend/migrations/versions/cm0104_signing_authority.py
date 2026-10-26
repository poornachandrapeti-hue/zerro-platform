"""Signing authority and delegation; cm0104 follows cm0103."""
from alembic import op
import sqlalchemy as sa
revision='cm0104'
down_revision='cm0103'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('contract_signing_authorities',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('max_value',sa.Numeric(20,2),nullable=False),
        sa.Column('valid_from',sa.DateTime(timezone=True),nullable=False),
        sa.Column('valid_until',sa.DateTime(timezone=True),nullable=False),
        sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('project_id','user_id','currency'))
    op.create_table('contract_signing_delegations',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('contract_id',sa.Integer,sa.ForeignKey('contract_register.id'),nullable=False),
        sa.Column('delegator_user_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('delegate_user_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('valid_from',sa.DateTime(timezone=True),nullable=False),
        sa.Column('valid_until',sa.DateTime(timezone=True),nullable=False),
        sa.Column('revoked_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))

def downgrade():
    op.drop_table('contract_signing_delegations')
    op.drop_table('contract_signing_authorities')
