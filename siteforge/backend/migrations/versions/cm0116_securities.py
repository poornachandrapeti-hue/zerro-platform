"""CM0116 security instruments and lifecycle history."""
from alembic import op
import sqlalchemy as sa
revision='cm0116'
down_revision='cm0115'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('contract_security_instruments',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('organization_id',sa.Integer,sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('contract_id',sa.Integer,sa.ForeignKey('contract_register.id'),nullable=False),
        sa.Column('instrument_type',sa.String(40),nullable=False),
        sa.Column('issuer',sa.String(240),nullable=False),
        sa.Column('reference_number',sa.String(120),nullable=False),
        sa.Column('amount',sa.Numeric(20,2),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('issue_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('required_valid_until',sa.DateTime(timezone=True)),
        sa.Column('renewal_owner_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('release_conditions',sa.Text,nullable=False),
        sa.Column('evidence_ref',sa.Text,nullable=False),
        sa.Column('status',sa.String(30),nullable=False),
        sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('contract_id','reference_number'))
    op.create_index('ix_contract_security_scope','contract_security_instruments',['organization_id','project_id','contract_id'])
    op.create_table('contract_security_events',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('instrument_id',sa.Integer,sa.ForeignKey('contract_security_instruments.id'),nullable=False),
        sa.Column('event_type',sa.String(30),nullable=False),
        sa.Column('old_expiry',sa.DateTime(timezone=True)),
        sa.Column('new_expiry',sa.DateTime(timezone=True)),
        sa.Column('evidence_ref',sa.Text,nullable=False),
        sa.Column('actor_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('recorded_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_contract_security_events_instrument','contract_security_events',['instrument_id'])

def downgrade():
    op.drop_index('ix_contract_security_events_instrument',table_name='contract_security_events')
    op.drop_table('contract_security_events')
    op.drop_index('ix_contract_security_scope',table_name='contract_security_instruments')
    op.drop_table('contract_security_instruments')
