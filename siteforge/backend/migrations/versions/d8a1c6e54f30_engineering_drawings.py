"""engineering drawings, transmittals and review stage purpose"""

import json

from alembic import op
import sqlalchemy as sa

revision = "d8a1c6e54f30"
down_revision = "c4d8e1a20b11"
branch_labels = None
depends_on = None

EXTRA = {
    "Project Manager": ["drawings.view"],
    "Engineering Engineer": ["drawings.view", "drawings.edit"],
    "Discipline Head": ["drawings.view", "drawings.edit", "drawings.review", "drawings.release"],
    "Client/PMC Reviewer": ["drawings.view", "drawings.client_review"],
    "Document Controller": ["drawings.view", "transmittals.issue"],
    "Site Engineer": ["drawings.view"],
}


def upgrade():
    op.add_column(
        "stored_files",
        sa.Column("scan_status", sa.String(length=20), server_default="available", nullable=False),
    )
    op.add_column(
        "approval_stages",
        sa.Column("purpose", sa.String(length=40), server_default="", nullable=False),
    )
    op.create_table(
        "drawings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=80), nullable=False),
        sa.Column("number_key", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("drawing_type", sa.String(length=80), nullable=False),
        sa.Column("discipline_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("responsible_user_id", sa.Integer(), nullable=True),
        sa.Column("area_id", sa.Integer(), nullable=True),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("preparation", sa.String(length=30), nullable=False),
        sa.Column("work_reference", sa.String(length=80), nullable=False),
        sa.Column("provenance", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["area_id"], ["areas.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["discipline_id"], ["disciplines.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["responsible_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "number_key"),
    )
    op.create_index("ix_drawings_organization_id", "drawings", ["organization_id"])
    op.create_index("ix_drawings_project_id", "drawings", ["project_id"])
    op.create_index("ix_drawings_discipline_id", "drawings", ["discipline_id"])
    op.create_table(
        "drawing_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("drawing_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("code_key", sa.String(length=20), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("review_state", sa.String(length=40), nullable=False),
        sa.Column("release_state", sa.String(length=30), nullable=False),
        sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["drawing_id"], ["drawings.id"]),
        sa.ForeignKeyConstraint(["file_id"], ["stored_files.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("drawing_id", "code_key"),
    )
    op.create_index("ix_drawing_revisions_drawing_id", "drawing_revisions", ["drawing_id"])
    op.create_table(
        "drawing_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.Column("page_ref", sa.String(length=80), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("closure_evidence", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["drawing_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_drawing_comments_revision_id", "drawing_comments", ["revision_id"])
    op.create_table(
        "transmittals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=80), nullable=False),
        sa.Column("number_key", sa.String(length=80), nullable=False),
        sa.Column("purpose", sa.String(length=200), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "number_key"),
    )
    op.create_index("ix_transmittals_project_id", "transmittals", ["project_id"])
    op.create_table(
        "transmittal_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transmittal_id", sa.Integer(), nullable=False),
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["revision_id"], ["drawing_revisions.id"]),
        sa.ForeignKeyConstraint(["transmittal_id"], ["transmittals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transmittal_items_transmittal_id", "transmittal_items", ["transmittal_id"])
    op.create_table(
        "transmittal_recipients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transmittal_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["transmittal_id"], ["transmittals.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transmittal_id", "user_id"),
    )
    op.create_index(
        "ix_transmittal_recipients_transmittal_id", "transmittal_recipients", ["transmittal_id"]
    )
    op.create_table(
        "revision_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("drawing_id", sa.Integer(), nullable=False),
        sa.Column("revision_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["drawing_id"], ["drawings.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["drawing_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_revision_events_project_id", "revision_events", ["project_id"])
    op.create_index("ix_revision_events_drawing_id", "revision_events", ["drawing_id"])
    op.create_index("ix_revision_events_revision_id", "revision_events", ["revision_id"])
    op.create_table(
        "wrench_settings",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("specification", sa.Text(), nullable=False),
        sa.Column("credential_label", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("project_id"),
    )
    op.create_table(
        "wrench_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("drawing_id", sa.Integer(), nullable=False),
        sa.Column("external_document_id", sa.String(length=120), nullable=False),
        sa.Column("external_revision_id", sa.String(length=120), nullable=False),
        sa.Column("provenance", sa.String(length=20), nullable=False),
        sa.Column("conflict_status", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["drawing_id"], ["drawings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("drawing_id"),
    )
    op.create_index("ix_wrench_links_drawing_id", "wrench_links", ["drawing_id"])
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, name, permissions FROM roles")).fetchall()
    for row in rows:
        add = EXTRA.get(row.name)
        if not add:
            continue
        current = row.permissions if isinstance(row.permissions, list) else json.loads(row.permissions or "[]")
        merged = list(current)
        for item in add:
            if item not in merged:
                merged.append(item)
        bind.execute(
            sa.text("UPDATE roles SET permissions = CAST(:permissions AS json) WHERE id = :id"),
            {"permissions": json.dumps(merged), "id": row.id},
        )


def downgrade():
    op.drop_index("ix_wrench_links_drawing_id", table_name="wrench_links")
    op.drop_table("wrench_links")
    op.drop_table("wrench_settings")
    op.drop_index("ix_revision_events_revision_id", table_name="revision_events")
    op.drop_index("ix_revision_events_drawing_id", table_name="revision_events")
    op.drop_index("ix_revision_events_project_id", table_name="revision_events")
    op.drop_table("revision_events")
    op.drop_index("ix_transmittal_recipients_transmittal_id", table_name="transmittal_recipients")
    op.drop_table("transmittal_recipients")
    op.drop_index("ix_transmittal_items_transmittal_id", table_name="transmittal_items")
    op.drop_table("transmittal_items")
    op.drop_index("ix_transmittals_project_id", table_name="transmittals")
    op.drop_table("transmittals")
    op.drop_index("ix_drawing_comments_revision_id", table_name="drawing_comments")
    op.drop_table("drawing_comments")
    op.drop_index("ix_drawing_revisions_drawing_id", table_name="drawing_revisions")
    op.drop_table("drawing_revisions")
    op.drop_index("ix_drawings_discipline_id", table_name="drawings")
    op.drop_index("ix_drawings_project_id", table_name="drawings")
    op.drop_index("ix_drawings_organization_id", table_name="drawings")
    op.drop_table("drawings")
    op.drop_column("approval_stages", "purpose")
    op.drop_column("stored_files", "scan_status")
