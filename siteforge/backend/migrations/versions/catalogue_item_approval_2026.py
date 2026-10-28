
"""Add catalogue approval state and immutable review history."""

from alembic import op
import sqlalchemy as sa


revision = "catalogue_appr_26"
down_revision = "catalogue_cfg_26"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add approval status.
    # New catalogue items must default to Draft.
    op.add_column(
        "procurement_items",
        sa.Column(
            "approval_status",
            sa.String(24),
            nullable=False,
            server_default="Draft",
        ),
    )

    # 2. Preserve existing active catalogue items.
    # These records existed before the new approval workflow.
    # Treat them as legacy-accepted, not newly approved by a user.
    op.execute(
        """
        UPDATE procurement_items
        SET approval_status = 'Approved'
        WHERE active = TRUE
        """
    )

    # 3. Track the user who submits an item for approval.
    op.add_column(
        "procurement_items",
        sa.Column(
            "submitted_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )

    # 4. Create immutable catalogue review history.
    op.create_table(
        "procurement_item_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("procurement_items.id"),
            nullable=False,
        ),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("item_version", sa.Integer(), nullable=False),
        sa.Column("specification_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "actor_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 5. Create review history indexes.
    op.create_index(
        "ix_procurement_item_reviews_org",
        "procurement_item_reviews",
        ["organization_id"],
    )

    op.create_index(
        "ix_procurement_item_reviews_item",
        "procurement_item_reviews",
        ["item_id"],
    )


def downgrade():
    op.drop_index(
        "ix_procurement_item_reviews_item",
        table_name="procurement_item_reviews",
    )

    op.drop_index(
        "ix_procurement_item_reviews_org",
        table_name="procurement_item_reviews",
    )

    op.drop_table("procurement_item_reviews")

    op.drop_column("procurement_items", "submitted_by")
    op.drop_column("procurement_items", "approval_status")
