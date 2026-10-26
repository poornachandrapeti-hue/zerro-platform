"""Opt-in scheduled progress alert monitoring settings."""
from alembic import op
import sqlalchemy as sa
revision='p18a1c4e7f725'
down_revision='p10a1c4e7f724'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('progress_alert_policies',sa.Column('enabled',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('progress_alert_policies',sa.Column('recipient_ids',sa.JSON(),nullable=False,server_default='[]'))
    op.add_column('progress_alert_policies',sa.Column('escalate_after_hours',sa.Integer(),nullable=False,server_default='24'))
    op.add_column('progress_alert_policies',sa.Column('last_scanned_at',sa.DateTime(timezone=True),nullable=True))

def downgrade():
    for name in ('last_scanned_at','escalate_after_hours','recipient_ids','enabled'):
        op.drop_column('progress_alert_policies',name)
