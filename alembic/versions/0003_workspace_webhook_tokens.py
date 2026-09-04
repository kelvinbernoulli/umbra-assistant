"""add hashed workspace webhook tokens"""

from alembic import op
import sqlalchemy as sa


revision = "0003_workspace_webhook_tokens"
down_revision = "0002_workspace_members"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("webhook_token_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("workspaces", "webhook_token_hash")
