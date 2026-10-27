"""P3C1F-E: audited inspection-to-attachment associations.
Revision ID: progress_p3c1fe_qa_files
Revises: progress_p3c1c_qty_verify
"""
from alembic import op
import sqlalchemy as sa
revision = 'progress_p3c1fe_qa_files'
down_revision = 'progress_p3c1c_qty_verify'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('progress_inspection_attachment_links',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('activity_id',sa.Integer(),nullable=False),
        sa.Column('inspection_id',sa.Integer(),nullable=False),
        sa.Column('progress_line_id',sa.Integer(),sa.ForeignKey('progress_lines.id'),nullable=False),
        sa.Column('project_file_id',sa.Integer(),sa.ForeignKey('project_files.id'),nullable=False),
        sa.Column('stored_file_id',sa.Integer(),sa.ForeignKey('stored_files.id'),nullable=False),
        sa.Column('content_digest',sa.String(64),nullable=False),
        sa.Column('status',sa.String(20),nullable=False,server_default='Proposed'),
        sa.Column('proposer_user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('reviewer_user_id',sa.Integer(),sa.ForeignKey('users.id')),
        sa.Column('review_note',sa.Text(),nullable=False,server_default=''),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('reviewed_at',sa.DateTime(timezone=True)),
        sa.Column('version',sa.Integer(),nullable=False,server_default='1'),
        sa.UniqueConstraint('organization_id','project_id','inspection_id','progress_line_id','project_file_id',name='uq_progress_inspection_attachment_scope'),
        sa.CheckConstraint("status IN ('Proposed','Approved','Rejected','Revoked')",name='ck_progress_inspection_attachment_status'),
        sa.CheckConstraint('version > 0',name='ck_progress_inspection_attachment_version'),
        sa.CheckConstraint('reviewer_user_id IS NULL OR reviewer_user_id <> proposer_user_id',name='ck_progress_inspection_attachment_independent'),
    )
    op.create_index('ix_progress_inspection_attachment_scope','progress_inspection_attachment_links',['organization_id','project_id','inspection_id'])
    op.create_table('progress_inspection_attachment_events',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('link_id',sa.Integer(),sa.ForeignKey('progress_inspection_attachment_links.id'),nullable=False),
        sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id'),nullable=False),
        sa.Column('project_id',sa.Integer(),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('action',sa.String(20),nullable=False),
        sa.Column('actor_user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('note',sa.Text(),nullable=False,server_default=''),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.CheckConstraint("action IN ('Proposed','Approved','Rejected','Revoked')",name='ck_progress_inspection_attachment_event_action'),
    )
    op.create_index('ix_progress_inspection_attachment_events_link','progress_inspection_attachment_events',['link_id'])

def downgrade():
    op.drop_index('ix_progress_inspection_attachment_events_link',table_name='progress_inspection_attachment_events')
    op.drop_table('progress_inspection_attachment_events')
    op.drop_index('ix_progress_inspection_attachment_scope',table_name='progress_inspection_attachment_links')
    op.drop_table('progress_inspection_attachment_links')
