"""create workspace-scoped transactional ingestion tables"""

from alembic import op
import sqlalchemy as sa


revision = "0001_transactional_ingestion"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "webhook_receipts",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("workspace_id", sa.String(length=255), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=512), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "provider", "external_id", name="uq_webhook_receipts_workspace_provider_external"),
    )
    op.create_index("ix_webhook_receipts_workspace_received", "webhook_receipts", ["workspace_id", "received_at"])
    op.create_table(
        "source_items",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("workspace_id", sa.String(length=255), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=512), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "source", "external_id", name="uq_source_items_workspace_source_external"),
    )
    op.create_index("ix_source_items_workspace_created", "source_items", ["workspace_id", "created_at"])
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("workspace_id", sa.String(length=255), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("receipt_id", sa.String(length=255), sa.ForeignKey("webhook_receipts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ingestion_jobs_workspace_status", "ingestion_jobs", ["workspace_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_ingestion_jobs_workspace_status", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_index("ix_source_items_workspace_created", table_name="source_items")
    op.drop_table("source_items")
    op.drop_index("ix_webhook_receipts_workspace_received", table_name="webhook_receipts")
    op.drop_table("webhook_receipts")
    op.drop_table("workspaces")