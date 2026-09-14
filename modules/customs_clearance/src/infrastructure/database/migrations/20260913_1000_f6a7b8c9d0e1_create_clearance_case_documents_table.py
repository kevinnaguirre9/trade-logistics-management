"""create clearance case documents table

Revision ID: f6a7b8c9d0e1
Revises: d4e5f6a7b8c9
Create Date: 2026-09-13 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "customs"

DOCUMENT_TYPES = (
    "COMMERCIAL_INVOICE",
    "BILL_OF_LADING",
)


def upgrade() -> None:
    """Create the document collection of the ClearanceCase aggregate."""
    allowed_types = ", ".join(f"'{document_type}'" for document_type in DOCUMENT_TYPES)

    op.create_table(
        "clearance_case_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "clearance_case_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        # No foreign key: the file belongs to the Files module, in another
        # schema, and is referenced by value only.
        sa.Column("file_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "is_verified",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "verified_by_inspector_id", sa.String(length=128), nullable=True
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
        sa.PrimaryKeyConstraint("id", name="pk_clearance_case_documents"),
        # Inside the aggregate, so this one is a real foreign key.
        sa.ForeignKeyConstraint(
            ["clearance_case_id"],
            [f"{SCHEMA}.clearance_cases.id"],
            name="fk_clearance_case_documents_clearance_case_id_clearance_cases",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            f"document_type IN ({allowed_types})",
            name="document_type",
        ),
        # An inspector is recorded only on a document that was actually cleared.
        sa.CheckConstraint(
            "is_verified OR verified_by_inspector_id IS NULL",
            name="inspector_only_when_verified",
        ),
        # One file is filed against a case once.
        sa.UniqueConstraint(
            "clearance_case_id",
            "file_uuid",
            name="uq_clearance_case_documents_case_file",
        ),
        schema=SCHEMA,
    )

    op.create_index(
        "ix_clearance_case_documents_clearance_case_id",
        "clearance_case_documents",
        ["clearance_case_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Drop the document collection."""
    op.drop_index(
        "ix_clearance_case_documents_clearance_case_id",
        table_name="clearance_case_documents",
        schema=SCHEMA,
    )
    op.drop_table("clearance_case_documents", schema=SCHEMA)
