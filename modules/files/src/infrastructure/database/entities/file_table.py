"""Table definitions of the StoredFile aggregate and its references."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from modules.files.src.domain.entities import MAX_FIELD_LENGTH
from modules.files.src.domain.stored_file import (
    MAX_CONTENT_TYPE_LENGTH,
    MAX_DISK_LENGTH,
)
from modules.files.src.domain.value_objects.storage_location import StorageLocation
from modules.files.src.infrastructure.database import SCHEMA
from modules.shared.database import metadata

files_table = sa.Table(
    "files",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    # Which storage class holds the bytes: "local", "gcp", "aws", "sftp", ...
    # A name rather than an enum, so adding a disk is configuration, not a
    # migration.
    sa.Column("disk", sa.String(MAX_DISK_LENGTH), nullable=False),
    # The two halves of the object key, kept apart because the caller supplies
    # them apart and reads them back the same way.
    sa.Column("path", sa.String(StorageLocation.MAX_PATH_LENGTH), nullable=False),
    sa.Column("name", sa.String(StorageLocation.MAX_NAME_LENGTH), nullable=False),
    sa.Column("size_bytes", sa.BigInteger, nullable=False),
    sa.Column("content_type", sa.String(MAX_CONTENT_TYPE_LENGTH), nullable=False),
    # "sha256:<hex>" of what was actually written, not what was announced.
    sa.Column("checksum", sa.String(128), nullable=False),
    sa.Column(
        "metadata",
        postgresql.JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    ),
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
    sa.CheckConstraint("size_bytes > 0", name="size_bytes_positive"),
    # One object key, one file: the location is chosen by the caller, so a
    # collision means two callers disagree about what lives there.
    sa.UniqueConstraint("disk", "path", "name", name="uq_files_disk_path_name"),
    schema=SCHEMA,
)

file_references_table = sa.Table(
    "file_references",
    metadata,
    sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column(
        "file_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(f"{SCHEMA}.files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    # What this file is about, in another bounded context. Plain values on
    # purpose: no foreign key crosses a schema.
    sa.Column("context", sa.String(MAX_FIELD_LENGTH), nullable=False),
    sa.Column("entity_type", sa.String(MAX_FIELD_LENGTH), nullable=False),
    # Both identifiers are optional: a reference may describe an external
    # entity that has files but no identifier of its own here.
    sa.Column("entity_id", sa.String(MAX_FIELD_LENGTH), nullable=True),
    sa.Column("entity_uuid", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    # NULLS NOT DISTINCT so the constraint still bites when the reference
    # carries no entity_id: without it PostgreSQL treats every NULL as unique
    # and the same reference could be declared any number of times.
    sa.UniqueConstraint(
        "file_id",
        "context",
        "entity_type",
        "entity_id",
        name="uq_file_references_file_id_owner",
        postgresql_nulls_not_distinct=True,
    ),
    schema=SCHEMA,
)

#: Answers "every file of this clearance case", the query the owning contexts
#: actually make.
file_references_owner_index = sa.Index(
    "ix_file_references_owner",
    file_references_table.c.context,
    file_references_table.c.entity_type,
    file_references_table.c.entity_id,
)
