"""add workspace membership records"""

from alembic import op
import sqlalchemy as sa


revision = "0002_workspace_members"
down_revision = "0001_transactional_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_members",
        sa.Column("workspace_id", sa.String(length=255), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.String(length=255), primary_key=True),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workspace_members")