"""Table definition of the DocumentRegistryItem entity."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from modules.customs_clearance.src.domain.entities import MAX_INSPECTOR_ID_LENGTH
from modules.customs_clearance.src.domain.enums import DocumentType
from modules.customs_clearance.src.infrastructure.database import SCHEMA
from modules.shared.database import metadata

#: Stored as VARCHAR with a CHECK rather than a native PostgreSQL enum, so
#: accepting another kind of paperwork stays an ordinary migration.
document_type_type = sa.Enum(
    DocumentType,
    name="document_type",
    native_enum=False,
    create_constraint=True,
    length=32,
    values_callable=lambda enum: [member.value for member in enum],
    validate_strings=True,
)

clearance_case_documents_table = sa.Table(
    "clearance_case_documents",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "clearance_case_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(f"{SCHEMA}.clearance_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("document_type", document_type_type, nullable=False),
    # The document itself belongs to the Files module: its identifier is stored
    # as a plain value, with no foreign key across schemas.
    sa.Column("file_uuid", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column(
        "is_verified",
        sa.Boolean,
        nullable=False,
        server_default=sa.false(),
    ),
    sa.Column(
        "verified_by_inspector_id",
        sa.String(MAX_INSPECTOR_ID_LENGTH),
        nullable=True,
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
    # One file is filed against a case once; attaching it twice is a caller
    # repeating itself, not a second document.
    sa.UniqueConstraint(
        "clearance_case_id",
        "file_uuid",
        name="uq_clearance_case_documents_case_file",
    ),
    # An inspector is recorded only on a document that was actually cleared.
    sa.CheckConstraint(
        "is_verified OR verified_by_inspector_id IS NULL",
        name="inspector_only_when_verified",
    ),
    schema=SCHEMA,
)
