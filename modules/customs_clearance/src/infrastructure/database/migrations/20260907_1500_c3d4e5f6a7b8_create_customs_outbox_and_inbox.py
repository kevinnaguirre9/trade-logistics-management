"""create customs outbox and inbox tables

Revision ID: c3d4e5f6a7b8
Revises:
Create Date: 2026-09-07 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("customs",)
depends_on: str | Sequence[str] | None = None

SCHEMA = "customs"

OUTBOX_STATUSES = ("Pending", "Sent")


def upgrade() -> None:
    """Create the transactional outbox and the inbox of this module."""
    allowed_statuses = ", ".join(f"'{status}'" for status in OUTBOX_STATUSES)

    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_type", sa.String(length=255), nullable=False),
        sa.Column("exchange", sa.String(length=255), nullable=False),
        sa.Column("routing_key", sa.String(length=255), nullable=False),
        sa.Column(
            "headers",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "properties",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("body", postgresql.JSONB(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="Pending",
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_messages"),
        sa.UniqueConstraint("message_id", name="uq_outbox_messages_message_id"),
        sa.CheckConstraint(
            f"status IN ({allowed_statuses})",
            name="ck_outbox_messages_outbox_status",
        ),
        schema=SCHEMA,
    )

    # The relay only ever reads the pending rows, oldest first.
    op.create_index(
        "ix_outbox_messages_status",
        "outbox_messages",
        ["status"],
        schema=SCHEMA,
    )

    op.create_table(
        "inbox_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_type", sa.String(length=255), nullable=False),
        sa.Column("handler_name", sa.String(length=255), nullable=False),
        sa.Column(
            "handled_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inbox_messages"),
        # Deduplication key: one message is handled at most once per handler.
        sa.UniqueConstraint(
            "message_id",
            "handler_name",
            name="uq_inbox_messages_message_id_handler_name",
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Drop the outbox and inbox of this module."""
    op.drop_table("inbox_messages", schema=SCHEMA)
    op.drop_index("ix_outbox_messages_status", table_name="outbox_messages", schema=SCHEMA)
    op.drop_table("outbox_messages", schema=SCHEMA)
