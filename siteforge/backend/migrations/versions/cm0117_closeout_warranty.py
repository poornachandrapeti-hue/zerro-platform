"""CM0117 closeout and warranty ledgers"""
from alembic import op
import sqlalchemy as sa
revision='cm0117'
down_revision='cm0116'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('contract_closeout_checks',
       sa.Column('id',sa.Integer,primary_key=True),
       sa.Column('organization_id',sa.Integer,sa.ForeignKey('organizations.id'),nullable=False),
       sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
       sa.Column('contract_id',sa.Integer,sa.ForeignKey('contract_register.id'),nullable=False),
       sa.Column('check_type',sa.String(50),nullable=False),
       sa.Column('status',sa.String(25),nullable=False),
       sa.Column('source_system',sa.String(40)),sa.Column('source_record_ref',sa.Text()),
       sa.Column('evidence_ref',sa.Text()),
       sa.Column('verified_by',sa.Integer,sa.ForeignKey('users.id')),
       sa.Column('verified_at',sa.DateTime(timezone=True)),
       sa.UniqueConstraint('contract_id','check_type'))
    op.create_table('contract_warranties',
       sa.Column('id',sa.Integer,primary_key=True),
       sa.Column('organization_id',sa.Integer,sa.ForeignKey('organizations.id'),nullable=False),
       sa.Column('project_id',sa.Integer,sa.ForeignKey('projects.id'),nullable=False),
       sa.Column('contract_id',sa.Integer,sa.ForeignKey('contract_register.id'),nullable=False),
       sa.Column('description',sa.Text(),nullable=False),
       sa.Column('owner_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
       sa.Column('due_at',sa.DateTime(timezone=True)),
       sa.Column('status',sa.String(30),nullable=False),
       sa.Column('evidence_ref',sa.Text()),
       sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
       sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))

def downgrade():
    op.drop_table('contract_warranties')
    op.drop_table('contract_closeout_checks')
