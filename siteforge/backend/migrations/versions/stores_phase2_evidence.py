"""Private stores receipt evidence links."""
import sqlalchemy as sa
from alembic import op
revision = "stores_phase2_evidence"
down_revision = "stores_phase2_intake"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("stores_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("document_type", sa.String(20), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("stored_files.id"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("document_type", "document_id", "file_id", name="uq_stores_evidence_document_file"))
    op.create_index("ix_stores_evidence_organization_id", "stores_evidence", ["organization_id"])
    op.create_index("ix_stores_evidence_project_id", "stores_evidence", ["project_id"])


def downgrade():
    op.drop_table("stores_evidence")
