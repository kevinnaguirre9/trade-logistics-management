"""create files and file references tables

Revision ID: e5f6a7b8c9d0
Revises:
Create Date: 2026-09-08 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("files",)
depends_on: str | Sequence[str] | None = None

SCHEMA = "files"


def upgrade() -> None:
    """Create the StoredFile aggregate and its reference collection."""
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        # Disk name rather than an enum: adding a storage class is
        # configuration, not a migration.
        sa.Column("disk", sa.String(length=32), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name="pk_files"),
        sa.CheckConstraint("size_bytes > 0", name="size_bytes_positive"),
        # One object key, one file: a collision means two callers disagree
        # about what lives there.
        sa.UniqueConstraint("disk", "path", "name", name="uq_files_disk_path_name"),
        schema=SCHEMA,
    )

    op.create_table(
        "file_references",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        # What the file is about lives in another bounded context, so these are
        # plain values: no foreign key crosses a schema.
        sa.Column("context", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=128), nullable=False),
        # Both identifiers are optional: a reference may describe an external
        # entity that has files but no identifier of its own here.
        sa.Column("entity_id", sa.String(length=128), nullable=True),
        sa.Column("entity_uuid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_file_references"),
        # Inside the aggregate, so this one is a real foreign key.
        sa.ForeignKeyConstraint(
            ["file_id"],
            [f"{SCHEMA}.files.id"],
            name="fk_file_references_file_id_files",
            ondelete="CASCADE",
        ),
        # NULLS NOT DISTINCT so the constraint still bites when the reference
        # carries no entity_id (PostgreSQL 15+).
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

    op.create_index(
        "ix_file_references_file_id",
        "file_references",
        ["file_id"],
        schema=SCHEMA,
    )
    # Answers "every file of this clearance case", the query owning contexts
    # actually make.
    op.create_index(
        "ix_file_references_owner",
        "file_references",
        ["context", "entity_type", "entity_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Drop the file tables."""
    op.drop_index(
        "ix_file_references_owner", table_name="file_references", schema=SCHEMA
    )
    op.drop_index(
        "ix_file_references_file_id", table_name="file_references", schema=SCHEMA
    )
    op.drop_table("file_references", schema=SCHEMA)
    op.drop_table("files", schema=SCHEMA)
