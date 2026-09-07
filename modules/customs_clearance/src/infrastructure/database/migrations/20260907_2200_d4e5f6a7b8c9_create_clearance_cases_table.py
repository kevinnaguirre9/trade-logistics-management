"""create clearance cases table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-07 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "customs"

ASSESSMENT_STATUSES = (
    "Opened",
    "DocumentVerification",
    "RiskAssessment",
    "DutyPaymentPending",
    "Released",
    "Rejected",
)


def upgrade() -> None:
    """Create the clearance case aggregate table."""
    allowed_statuses = ", ".join(f"'{status}'" for status in ASSESSMENT_STATUSES)

    op.create_table(
        "clearance_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        # No foreign key: the shipment belongs to another bounded context and
        # is referenced by value only.
        sa.Column("shipment_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("declaration_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("declaration_currency", sa.String(length=3), nullable=True),
        sa.Column("duty_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("duty_currency", sa.String(length=3), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_clearance_cases"),
        sa.CheckConstraint(
            f"status IN ({allowed_statuses})",
            name="assessment_status",
        ),
        sa.CheckConstraint(
            "(declaration_amount IS NULL) = (declaration_currency IS NULL)",
            name="declaration_value_complete",
        ),
        sa.CheckConstraint(
            "(duty_amount IS NULL) = (duty_currency IS NULL)",
            name="duty_fee_complete",
        ),
        schema=SCHEMA,
    )

    op.create_index(
        "ix_clearance_cases_shipment_id",
        "clearance_cases",
        ["shipment_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_clearance_cases_status",
        "clearance_cases",
        ["status"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Drop the clearance case aggregate table."""
    op.drop_index(
        "ix_clearance_cases_status", table_name="clearance_cases", schema=SCHEMA
    )
    op.drop_index(
        "ix_clearance_cases_shipment_id", table_name="clearance_cases", schema=SCHEMA
    )
    op.drop_table("clearance_cases", schema=SCHEMA)
