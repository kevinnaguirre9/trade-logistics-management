"""create shipments table

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-09-06 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("shipment",)
depends_on: str | Sequence[str] | None = None

SCHEMA = "shipment"

TRACKING_STATUSES = (
    "Draft",
    "ReadyForManifest",
    "AwaitingCustomsRelease",
    "InTransit",
    "Delivered",
    "ExceptionHeld",
)


def upgrade() -> None:
    """Create the shipment aggregate table and its waybill serial sequence."""
    op.execute(
        "CREATE SEQUENCE IF NOT EXISTS shipment.waybill_serial "
        "START WITH 1 MINVALUE 1 MAXVALUE 9999999"
    )

    allowed_statuses = ", ".join(f"'{status}'" for status in TRACKING_STATUSES)

    op.create_table(
        "shipments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("waybill_number", sa.String(length=12), nullable=False),
        # Cargo manifest value object: NULL until the manifest is finalized.
        sa.Column("total_weight_kg", sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column("total_volume_cbm", sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column("commodity_code", sa.String(length=16), nullable=True),
        # Shipment route value object.
        sa.Column("origin_port_code", sa.String(length=5), nullable=False),
        sa.Column("destination_port_code", sa.String(length=5), nullable=False),
        sa.Column(
            "transit_legs",
            postgresql.ARRAY(sa.String(length=5)),
            server_default=sa.text("'{}'::character varying[]"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("exception_reason", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_shipments"),
        sa.UniqueConstraint("waybill_number", name="uq_shipments_waybill_number"),
        sa.CheckConstraint(
            f"status IN ({allowed_statuses})",
            name="tracking_status",
        ),
        sa.CheckConstraint(
            "origin_port_code <> destination_port_code",
            name="route_endpoints_differ",
        ),
        schema=SCHEMA,
    )

    op.create_index(
        "ix_shipments_status",
        "shipments",
        ["status"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Drop the shipment aggregate table and its sequence."""
    op.drop_index("ix_shipments_status", table_name="shipments", schema=SCHEMA)
    op.drop_table("shipments", schema=SCHEMA)
    op.execute("DROP SEQUENCE IF EXISTS shipment.waybill_serial")
