"""rfq quotations and awards"""

import sqlalchemy as sa
from alembic import op

revision = "e7a1c4b83d55"
down_revision = "c8f3a1d64e20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "request_for_quotations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("requisition_id", sa.Integer(), sa.ForeignKey("purchase_requisitions.id"), nullable=False),
        sa.Column("number", sa.String(80), nullable=False),
        sa.Column("number_key", sa.String(80), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id"), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("delivery_location", sa.String(300), nullable=False, server_default=""),
        sa.Column("technical_requirements", sa.Text(), nullable=False, server_default=""),
        sa.Column("commercial_requirements", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="Draft"),
        sa.Column("comparison_currency", sa.String(8), nullable=False, server_default=""),
        sa.Column("rate_date", sa.Date(), nullable=True),
        sa.Column("award_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("cancellation_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "number_key", name="uq_rfq_number"),
    )
    op.create_index("ix_request_for_quotations_project_id", "request_for_quotations", ["project_id"])
    op.create_table(
        "rfq_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rfq_id", sa.Integer(), sa.ForeignKey("request_for_quotations.id"), nullable=False),
        sa.Column("requisition_line_id", sa.Integer(), sa.ForeignKey("purchase_requisition_lines.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
    )
    op.create_index("ix_rfq_lines_rfq_id", "rfq_lines", ["rfq_id"])
    op.create_table(
        "rfq_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rfq_id", sa.Integer(), sa.ForeignKey("request_for_quotations.id"), nullable=False),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("procurement_vendors.id"), nullable=False),
        sa.UniqueConstraint("rfq_id", "vendor_id", name="uq_rfq_invite"),
    )
    op.create_index("ix_rfq_invites_rfq_id", "rfq_invites", ["rfq_id"])
    op.create_table(
        "vendor_quotations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rfq_id", sa.Integer(), sa.ForeignKey("request_for_quotations.id"), nullable=False),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("procurement_vendors.id"), nullable=False),
        sa.Column("reference", sa.String(80), nullable=False),
        sa.Column("quotation_date", sa.Date(), nullable=False),
        sa.Column("validity_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("freight", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("payment_terms", sa.String(300), nullable=False, server_default=""),
        sa.Column("technical_deviations", sa.Text(), nullable=False, server_default=""),
        sa.Column("conversion_rate", sa.Numeric(14, 6), nullable=True),
        sa.Column("technical_decision", sa.String(40), nullable=False, server_default=""),
        sa.Column("technical_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("technical_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("commercial_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("commercial_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("rfq_id", "vendor_id", name="uq_vendor_quotation"),
    )
    op.create_index("ix_vendor_quotations_rfq_id", "vendor_quotations", ["rfq_id"])
    op.create_table(
        "quotation_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quotation_id", sa.Integer(), sa.ForeignKey("vendor_quotations.id"), nullable=False),
        sa.Column("rfq_line_id", sa.Integer(), sa.ForeignKey("rfq_lines.id"), nullable=False),
        sa.Column("specification", sa.Text(), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("lead_time_days", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_quotation_lines_quotation_id", "quotation_lines", ["quotation_id"])
    op.create_table(
        "rfq_awards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rfq_id", sa.Integer(), sa.ForeignKey("request_for_quotations.id"), nullable=False),
        sa.Column("quotation_line_id", sa.Integer(), sa.ForeignKey("quotation_lines.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("awarded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rfq_awards_rfq_id", "rfq_awards", ["rfq_id"])
    from sqlalchemy.orm import Session

    from app.domains.identity_projects.seed import grant_role_permissions

    session = Session(bind=op.get_bind())
    grant_role_permissions(session)
    session.flush()


def downgrade():
    pass
