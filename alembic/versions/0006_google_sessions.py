"""Google users, one-use login challenges and revocable browser sessions."""
from alembic import op
import sqlalchemy as sa

revision = "0006_google_sessions"
down_revision = "0005_workspace_integrations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("google_users",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("google_sub", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("workspace_id", sa.String(255), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("api_key_id", sa.String(255), sa.ForeignKey("api_keys.id"), nullable=False))
    op.create_table("browser_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(255), sa.ForeignKey("google_users.id"), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False))
    op.create_index("ix_browser_sessions_expires_at", "browser_sessions", ["expires_at"])
    op.create_table("login_challenges",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.Integer(), nullable=False))
    op.create_index("ix_login_challenges_expires_at", "login_challenges", ["expires_at"])


def downgrade():
    op.drop_table("login_challenges")
    op.drop_table("browser_sessions")
    op.drop_table("google_users")
