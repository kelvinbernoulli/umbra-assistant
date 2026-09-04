"""add provider-to-workspace webhook mappings"""

from alembic import op
import sqlalchemy as sa


revision = "0005_workspace_integrations"
down_revision = "0004_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_integrations",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("workspace_id", sa.String(length=255), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workspace_integrations_workspace_provider", "workspace_integrations", ["workspace_id", "provider"])


def downgrade() -> None:
    op.drop_index("ix_workspace_integrations_workspace_provider", table_name="workspace_integrations")
    op.drop_table("workspace_integrations")