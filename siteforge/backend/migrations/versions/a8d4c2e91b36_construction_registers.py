"""construction templates, work packages, activities, and items"""

import sqlalchemy as sa
from alembic import op

revision = "a8d4c2e91b36"
down_revision = "b7e3c9a15d40"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "construction_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("code_key", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("prerequisites", sa.Text(), nullable=False, server_default=""),
        sa.Column("required_evidence", sa.Text(), nullable=False, server_default=""),
        sa.Column("checkpoints", sa.JSON(), nullable=False),
        sa.Column("progress_method", sa.String(40), nullable=False),
        sa.Column("completion_conditions", sa.Text(), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "code_key", name="uq_construction_template_code"),
        sa.CheckConstraint(
            "progress_method IN ('Quantity', 'Item completion', 'Weighted milestones')",
            name="ck_construction_template_method",
        ),
    )
    op.create_index("ix_construction_templates_project_id", "construction_templates", ["project_id"])
    op.create_table(
        "work_packages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("code_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=False),
        sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=False),
        sa.Column("scope_description", sa.Text(), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("responsible_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("supervisor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="Normal"),
        sa.Column("planning_reference", sa.String(120), nullable=False, server_default=""),
        sa.Column("planned_start", sa.Date(), nullable=True),
        sa.Column("planned_finish", sa.Date(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(30), nullable=False, server_default="Draft"),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "code_key", name="uq_work_package_code"),
        sa.CheckConstraint("priority IN ('Normal', 'High', 'Critical')", name="ck_work_package_priority"),
        sa.CheckConstraint(
            "status IN ('Draft', 'Ready', 'In Progress', 'On Hold', 'Physically Complete', "
            "'Accepted', 'Handed Over', 'Cancelled')",
            name="ck_work_package_status",
        ),
    )
    op.create_index("ix_work_packages_project_id", "work_packages", ["project_id"])
    op.create_table(
        "work_package_drawings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=False),
        sa.Column("revision_id", sa.Integer(), sa.ForeignKey("drawing_revisions.id"), nullable=False),
        sa.UniqueConstraint("package_id", "revision_id", name="uq_work_package_revision"),
    )
    op.create_index("ix_work_package_drawings_package_id", "work_package_drawings", ["package_id"])
    op.create_table(
        "work_package_requirements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=False),
        sa.Column("requirement_id", sa.Integer(), sa.ForeignKey("material_requirements.id"), nullable=False),
        sa.UniqueConstraint("package_id", "requirement_id", name="uq_work_package_requirement"),
    )
    op.create_index("ix_work_package_requirements_package_id", "work_package_requirements", ["package_id"])
    op.create_table(
        "construction_activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("work_packages.id"), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("construction_templates.id"), nullable=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("code_key", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("baseline_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("responsible_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("drawing_revision_id", sa.Integer(), sa.ForeignKey("drawing_revisions.id"), nullable=True),
        sa.Column("measurement_method", sa.String(40), nullable=False),
        sa.Column("progress_weight", sa.Numeric(6, 2), nullable=True),
        sa.Column("target_start", sa.Date(), nullable=True),
        sa.Column("target_finish", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "code_key", name="uq_construction_activity_code"),
        sa.CheckConstraint(
            "measurement_method IN ('Quantity', 'Item completion', 'Weighted milestones')",
            name="ck_construction_activity_method",
        ),
    )
    op.create_index("ix_construction_activities_project_id", "construction_activities", ["project_id"])
    op.create_index("ix_construction_activities_package_id", "construction_activities", ["package_id"])
    op.create_table(
        "construction_predecessors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=False),
        sa.Column("predecessor_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=False),
        sa.UniqueConstraint("activity_id", "predecessor_id", name="uq_construction_predecessor"),
        sa.CheckConstraint("activity_id <> predecessor_id", name="ck_construction_predecessor_self"),
    )
    op.create_index("ix_construction_predecessors_activity_id", "construction_predecessors", ["activity_id"])
    op.create_table(
        "construction_scope_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=False),
        sa.Column("previous_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("new_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_construction_scope_changes_activity_id", "construction_scope_changes", ["activity_id"])
    op.create_table(
        "construction_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("construction_activities.id"), nullable=False),
        sa.Column("identifier", sa.String(80), nullable=False),
        sa.Column("identifier_key", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("item_kind", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=True),
        sa.Column("drawing_revision_id", sa.Integer(), sa.ForeignKey("drawing_revisions.id"), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "identifier_key", name="uq_construction_item_identifier"),
        sa.CheckConstraint(
            "item_kind IN ('Pile', 'Foundation', 'Equipment', 'Cable', 'Instrument', 'Spool', 'Joint', 'Other')",
            name="ck_construction_item_kind",
        ),
    )
    op.create_index("ix_construction_items_project_id", "construction_items", ["project_id"])
    op.create_index("ix_construction_items_activity_id", "construction_items", ["activity_id"])

    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
