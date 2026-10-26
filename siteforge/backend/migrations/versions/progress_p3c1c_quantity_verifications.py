"""P3C1C draft/approved quantity verification and decision audit schema.

Revision ID: progress_p3c1c_qty_verify
Revises: progress_p2c2a_evidence_links
"""
from alembic import op
import sqlalchemy as sa

revision = 'progress_p3c1c_qty_verify'
down_revision = 'progress_p2c2a_evidence_links'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'progress_quantity_verifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('report_id', sa.Integer(), sa.ForeignKey('progress_reports.id'), nullable=False),
        sa.Column('progress_line_id', sa.Integer(), sa.ForeignKey('progress_lines.id'), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=False),
        sa.Column('baseline_revision_id', sa.Integer(), nullable=False),
        sa.Column('source_revision', sa.String(100), nullable=False),
        sa.Column('verification_reference', sa.String(240), nullable=False),
        sa.Column('unit', sa.String(40), nullable=False),
        sa.Column('verified_quantity', sa.Numeric(14, 3), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='Proposed'),
        sa.Column('proposer_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('reviewer_user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('review_note', sa.Text(), nullable=False, server_default=''),
        sa.Column('verified_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.UniqueConstraint('organization_id', 'project_id', 'progress_line_id', 'baseline_revision_id', 'source_revision', name='uq_progress_qty_verification_revision'),
        sa.CheckConstraint("status IN ('Proposed', 'Approved', 'Rejected', 'Revoked')", name='ck_progress_qty_verification_status'),
        sa.CheckConstraint('verified_quantity > 0', name='ck_progress_qty_verification_positive'),
        sa.CheckConstraint('version > 0', name='ck_progress_qty_verification_version'),
        sa.CheckConstraint('reviewer_user_id IS NULL OR reviewer_user_id <> proposer_user_id', name='ck_progress_qty_verification_independent'),
    )
    for col in ('organization_id', 'project_id', 'progress_line_id'):
        op.create_index(f'ix_progress_qty_verification_{col}', 'progress_quantity_verifications', [col])
    op.create_table(
        'progress_quantity_verification_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('verification_id', sa.Integer(), sa.ForeignKey('progress_quantity_verifications.id'), nullable=False),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('note', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("action IN ('Proposed', 'Approved', 'Rejected', 'Revoked')", name='ck_progress_qty_verification_event_action'),
    )
    op.create_index('ix_progress_qty_verification_event_parent', 'progress_quantity_verification_events', ['verification_id'])


def downgrade():
    op.drop_index('ix_progress_qty_verification_event_parent', table_name='progress_quantity_verification_events')
    op.drop_table('progress_quantity_verification_events')
    for col in ('progress_line_id', 'project_id', 'organization_id'):
        op.drop_index(f'ix_progress_qty_verification_{col}', table_name='progress_quantity_verifications')
    op.drop_table('progress_quantity_verifications')
