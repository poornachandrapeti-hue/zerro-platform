"""engineering register fields, categories, and release setting"""

import sqlalchemy as sa
from alembic import op

revision = "a1c7e4b92d08"
down_revision = "f6b2d1c84a17"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "drawing_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("name_key", sa.String(120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("discipline_id", "name_key", name="uq_drawing_categories_discipline_name"),
    )
    op.create_index("ix_drawing_categories_discipline_id", "drawing_categories", ["discipline_id"])
    op.create_table(
        "drawing_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("drawing_id", sa.Integer(), sa.ForeignKey("drawings.id"), nullable=False),
        sa.Column("related_id", sa.Integer(), sa.ForeignKey("drawings.id"), nullable=False),
        sa.UniqueConstraint("drawing_id", "related_id", name="uq_drawing_links_pair"),
    )
    op.create_index("ix_drawing_links_project_id", "drawing_links", ["project_id"])
    op.create_index("ix_drawing_links_drawing_id", "drawing_links", ["drawing_id"])
    op.create_table(
        "engineering_settings",
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), primary_key=True),
        sa.Column("allow_release_with_comments", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("drawings", sa.Column("category_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_drawings_category_id", "drawings", "drawing_categories", ["category_id"], ["id"]
    )
    op.add_column("drawings", sa.Column("reviewer_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_drawings_reviewer_id", "drawings", "users", ["reviewer_id"], ["id"])
    op.add_column("drawings", sa.Column("planned_submission", sa.Date(), nullable=True))
    op.add_column("drawings", sa.Column("planned_approval", sa.Date(), nullable=True))
    op.add_column("drawings", sa.Column("remarks", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "drawings",
        sa.Column("record_status", sa.String(20), nullable=False, server_default="Active"),
    )
    op.add_column(
        "drawings",
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column("drawing_revisions", sa.Column("description", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "drawing_revisions",
        sa.Column("issue_purpose", sa.String(30), nullable=False, server_default="Review"),
    )
    op.add_column("drawing_revisions", sa.Column("released_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_drawing_revisions_released_by", "drawing_revisions", "users", ["released_by"], ["id"]
    )
    op.add_column("drawing_revisions", sa.Column("released_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "drawing_revisions",
        sa.Column("release_reference", sa.String(120), nullable=False, server_default=""),
    )
    op.add_column(
        "drawing_revisions",
        sa.Column("client_outcome", sa.String(40), nullable=False, server_default=""),
    )
    op.add_column(
        "drawing_revisions",
        sa.Column("external_reviewer", sa.String(200), nullable=False, server_default=""),
    )
    op.add_column(
        "drawing_revisions",
        sa.Column("decision_reference", sa.String(200), nullable=False, server_default=""),
    )
    op.add_column("drawing_revisions", sa.Column("decision_recorded_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_drawing_revisions_decision_recorded_by",
        "drawing_revisions",
        "users",
        ["decision_recorded_by"],
        ["id"],
    )
    op.add_column(
        "drawing_comments",
        sa.Column("comment_number", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "drawing_comments",
        sa.Column("stage", sa.String(20), nullable=False, server_default="Internal"),
    )
    op.add_column("drawing_comments", sa.Column("closed_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_drawing_comments_closed_by", "drawing_comments", "users", ["closed_by"], ["id"]
    )
    op.add_column("drawing_comments", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("transmittals", sa.Column("sender_company_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_transmittals_sender_company", "transmittals", "companies", ["sender_company_id"], ["id"]
    )
    op.add_column("transmittals", sa.Column("recipient_company_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_transmittals_recipient_company",
        "transmittals",
        "companies",
        ["recipient_company_id"],
        ["id"],
    )
    op.add_column("transmittals", sa.Column("expected_response", sa.Date(), nullable=True))
    op.add_column("transmittals", sa.Column("method", sa.String(40), nullable=False, server_default=""))
    op.add_column(
        "transmittals",
        sa.Column("external_reference", sa.String(120), nullable=False, server_default=""),
    )
    from sqlalchemy.orm import Session

    from app.domains.engineering_documents.workflow import ensure_categories
    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    ensure_categories(session)
    session.execute(
        sa.text(
            "UPDATE drawing_revisions SET client_outcome = 'Approved' "
            "WHERE review_state = 'Accepted' AND client_outcome = ''"
        )
    )
    session.execute(
        sa.text(
            "UPDATE drawing_revisions SET client_outcome = 'Approved with Comments' "
            "WHERE review_state = 'Accepted with Comments' AND client_outcome = ''"
        )
    )
    session.flush()


def downgrade():
    op.drop_column("transmittals", "external_reference")
    op.drop_column("transmittals", "method")
    op.drop_column("transmittals", "expected_response")
    op.drop_constraint("fk_transmittals_recipient_company", "transmittals", type_="foreignkey")
    op.drop_column("transmittals", "recipient_company_id")
    op.drop_constraint("fk_transmittals_sender_company", "transmittals", type_="foreignkey")
    op.drop_column("transmittals", "sender_company_id")
    op.drop_column("drawing_comments", "closed_at")
    op.drop_constraint("fk_drawing_comments_closed_by", "drawing_comments", type_="foreignkey")
    op.drop_column("drawing_comments", "closed_by")
    op.drop_column("drawing_comments", "stage")
    op.drop_column("drawing_comments", "comment_number")
    op.drop_constraint(
        "fk_drawing_revisions_decision_recorded_by", "drawing_revisions", type_="foreignkey"
    )
    op.drop_column("drawing_revisions", "decision_recorded_by")
    op.drop_column("drawing_revisions", "decision_reference")
    op.drop_column("drawing_revisions", "external_reviewer")
    op.drop_column("drawing_revisions", "client_outcome")
    op.drop_column("drawing_revisions", "release_reference")
    op.drop_column("drawing_revisions", "released_at")
    op.drop_constraint("fk_drawing_revisions_released_by", "drawing_revisions", type_="foreignkey")
    op.drop_column("drawing_revisions", "released_by")
    op.drop_column("drawing_revisions", "issue_purpose")
    op.drop_column("drawing_revisions", "description")
    op.drop_column("drawings", "cancellation_reason")
    op.drop_column("drawings", "record_status")
    op.drop_column("drawings", "remarks")
    op.drop_column("drawings", "planned_approval")
    op.drop_column("drawings", "planned_submission")
    op.drop_constraint("fk_drawings_reviewer_id", "drawings", type_="foreignkey")
    op.drop_column("drawings", "reviewer_id")
    op.drop_constraint("fk_drawings_category_id", "drawings", type_="foreignkey")
    op.drop_column("drawings", "category_id")
    op.drop_table("engineering_settings")
    op.drop_table("drawing_links")
    op.drop_index("ix_drawing_categories_discipline_id", table_name="drawing_categories")
    op.drop_table("drawing_categories")
