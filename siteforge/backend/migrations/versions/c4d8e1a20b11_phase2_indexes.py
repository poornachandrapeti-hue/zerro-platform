"""add phase 2 foreign-key indexes"""

from alembic import op

revision = "c4d8e1a20b11"
down_revision = "b7e1c0a94f22"
branch_labels = None
depends_on = None


INDEXES = [
    ("ix_approval_policies_organization_id", "approval_policies", ["organization_id"]),
    ("ix_approval_stages_policy_id", "approval_stages", ["policy_id"]),
    ("ix_approval_reviewers_stage_id", "approval_reviewers", ["stage_id"]),
    ("ix_review_instances_organization_id", "review_instances", ["organization_id"]),
    ("ix_review_decisions_instance_id", "review_decisions", ["instance_id"]),
    ("ix_tasks_organization_id", "tasks", ["organization_id"]),
    ("ix_notifications_organization_id", "notifications", ["organization_id"]),
    ("ix_reminder_policies_project_id", "reminder_policies", ["project_id"]),
]


def upgrade():
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade():
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)
