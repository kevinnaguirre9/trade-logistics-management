"""Table definition of the ClearanceCase aggregate."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from modules.customs_clearance.src.domain.enums import AssessmentStatus
from modules.customs_clearance.src.infrastructure.database import SCHEMA
from modules.shared.database import metadata

#: Stored as VARCHAR with a CHECK rather than a native PostgreSQL enum: adding
#: a state stays an ordinary migration instead of an ALTER TYPE.
assessment_status_type = sa.Enum(
    AssessmentStatus,
    name="assessment_status",
    native_enum=False,
    create_constraint=True,
    length=32,
    values_callable=lambda enum: [member.value for member in enum],
    validate_strings=True,
)

clearance_cases_table = sa.Table(
    "clearance_cases",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    # The shipment lives in another bounded context: its identifier is stored
    # as a plain value, with no foreign key across schemas.
    sa.Column("shipment_id", sa.String(64), nullable=False, index=True),
    sa.Column("status", assessment_status_type, nullable=False, index=True),
    # Declared value: unknown until the documents are attached.
    sa.Column("declaration_amount", sa.Numeric(14, 2), nullable=True),
    sa.Column("declaration_currency", sa.String(3), nullable=True),
    # Duty fee: computed by the risk assessment.
    sa.Column("duty_amount", sa.Numeric(14, 2), nullable=True),
    sa.Column("duty_currency", sa.String(3), nullable=True),
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
    schema=SCHEMA,
)
