"""``shipment.shipments`` table definition."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from modules.shared.database import metadata
from modules.shipment.src.domain.enums import TrackingStatus
from modules.shipment.src.infrastructure.database import SCHEMA

#: Stored as VARCHAR guarded by a CHECK constraint instead of a native
#: PostgreSQL ENUM, so adding a status later is a plain constraint change.
tracking_status_type = sa.Enum(
    TrackingStatus,
    name="tracking_status",
    native_enum=False,
    create_constraint=True,
    length=32,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
    validate_strings=True,
)

shipments_table = sa.Table(
    "shipments",
    metadata,
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("waybill_number", sa.String(12), nullable=False, unique=True),
    # Cargo manifest value object (NULL until the manifest is finalized).
    sa.Column("total_weight_kg", sa.Numeric(14, 3, asdecimal=False), nullable=True),
    sa.Column("total_volume_cbm", sa.Numeric(14, 3, asdecimal=False), nullable=True),
    sa.Column("commodity_code", sa.String(16), nullable=True),
    # Shipment route value object.
    sa.Column("origin_port_code", sa.String(5), nullable=False),
    sa.Column("destination_port_code", sa.String(5), nullable=False),
    sa.Column(
        "transit_legs",
        postgresql.ARRAY(sa.String(5)),
        nullable=False,
        server_default=sa.text("'{}'::character varying[]"),
    ),
    sa.Column("status", tracking_status_type, nullable=False, index=True),
    sa.Column("exception_reason", sa.Text(), nullable=True),
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

#: Serial feeding the ``MUST-0000000`` waybill series.
waybill_serial_sequence = sa.Sequence(
    "waybill_serial",
    schema=SCHEMA,
    start=1,
    minvalue=1,
    maxvalue=9_999_999,
    metadata=metadata,
)
