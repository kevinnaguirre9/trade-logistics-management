"""Outbox and inbox tables, shared by every module schema.

Each module owns its own copy of these tables inside its own schema, as the
constraints require. Rather than declaring the same table twice, the tables are
defined without a schema and the *worker* selects one at runtime through
SQLAlchemy's ``schema_translate_map`` (see
:func:`modules.shared.message_bus.session.module_session_factory`). One
definition, one imperative mapping, two physical tables.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from modules.shared.database import mapper_registry, metadata
from modules.shared.message_bus.inbox.inbox_message import InboxMessage
from modules.shared.message_bus.outbox.outbox_message import OutboxMessage, OutboxStatus

outbox_status_type = sa.Enum(
    OutboxStatus,
    name="outbox_status",
    native_enum=False,
    create_constraint=True,
    length=16,
    values_callable=lambda enum: [member.value for member in enum],
    validate_strings=True,
)

outbox_messages_table = sa.Table(
    "outbox_messages",
    metadata,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column(
        "message_id",
        postgresql.UUID(as_uuid=True),
        nullable=False,
        unique=True,
    ),
    sa.Column("message_type", sa.String(255), nullable=False),
    sa.Column("exchange", sa.String(255), nullable=False),
    sa.Column("routing_key", sa.String(255), nullable=False),
    sa.Column(
        "headers",
        postgresql.JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    ),
    sa.Column(
        "properties",
        postgresql.JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    ),
    sa.Column("body", postgresql.JSONB, nullable=False),
    sa.Column(
        "status",
        outbox_status_type,
        nullable=False,
        server_default=OutboxStatus.PENDING.value,
        index=True,
    ),
    sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    ),
)

inbox_messages_table = sa.Table(
    "inbox_messages",
    metadata,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("message_type", sa.String(255), nullable=False),
    sa.Column("handler_name", sa.String(255), nullable=False),
    sa.Column(
        "handled_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    # Deduplication key: a message is handled at most once per handler.
    sa.UniqueConstraint(
        "message_id",
        "handler_name",
        name="uq_inbox_messages_message_id_handler_name",
    ),
)

_mappers_started = False


def start_message_bus_mappers() -> None:
    """Attach the outbox and inbox tables to their plain Python classes."""
    global _mappers_started
    if _mappers_started:
        return

    mapper_registry.map_imperatively(OutboxMessage, outbox_messages_table)
    mapper_registry.map_imperatively(InboxMessage, inbox_messages_table)

    _mappers_started = True


__all__ = [
    "inbox_messages_table",
    "outbox_messages_table",
    "outbox_status_type",
    "start_message_bus_mappers",
]
