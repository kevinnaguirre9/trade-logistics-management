"""HTTP controller of the *finalize cargo manifest* slice.

``POST /shipments/{shipment_id}/finalize-manifest``
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from modules.shared.database import get_session
from modules.shared.http.hateoas import HypermediaResponse, Link
from modules.shared.message_bus import OutboxMessageRepository
from modules.shared.message_bus.session import bind_module_schema
from modules.shipment.src.domain.enums import TrackingStatus
from modules.shipment.src.domain.shipment import ROUTE_LOCKED_STATUSES, Shipment
from modules.shipment.src.features.finalize_manifest.finalize_manifest_command import (
    FinalizeManifestCommand,
)
from modules.shipment.src.features.finalize_manifest.finalize_manifest_handler import (
    FinalizeManifestHandler,
)
from modules.shipment.src.infrastructure.database import SCHEMA
from modules.shipment.src.infrastructure.repositories import (
    PostgresShipmentRepository,
)

router = APIRouter()


class ManifestView(BaseModel):
    """Read model of the cargo now declared for the shipment."""

    total_weight_kg: float = Field(description="Gross weight, in kilograms.")
    total_volume_cbm: float = Field(description="Gross volume, in cubic metres.")
    commodity_code: str = Field(description="Customs classification of the goods.")


class FinalizeManifestResponse(HypermediaResponse):
    """The shipment once its cargo is declared, plus the tasks allowed next."""

    model_config = ConfigDict(populate_by_name=True)

    shipment_id: str = Field(description="Identifier of the shipment.")
    waybill_number: str = Field(description="Carrier tracking number.")
    status: TrackingStatus = Field(description="Lifecycle status of the shipment.")
    manifest: ManifestView = Field(description="Cargo declared for the shipment.")


async def get_finalize_manifest_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FinalizeManifestHandler:
    """Build the handler with its PostgreSQL-backed collaborators.

    The session is bound to this module schema first: the outbox table is
    declared without one, so the write has to be told which module it belongs
    to before the request touches the database.
    """
    await bind_module_schema(session, SCHEMA)

    return FinalizeManifestHandler(
        shipments=PostgresShipmentRepository(session),
        outbox=OutboxMessageRepository(session),
    )


def _next_tasks(shipment: Shipment) -> list[Link]:
    """Return the tasks allowed on the shipment in its current state."""
    shipment_id = str(shipment.id)

    tasks: list[Link] = []

    # The manifest is declared but the cargo has not moved yet, so the route
    # can still be redrawn until customs takes over.
    if shipment.status not in ROUTE_LOCKED_STATUSES:
        tasks.append(
            Link(
                rel="assign-route",
                href=f"/shipments/{shipment_id}/route",
                method="PUT",
            )
        )

    tasks.append(
        Link(
            rel="flag-exception",
            href=f"/shipments/{shipment_id}/flag-exception",
            method="POST",
        )
    )

    return tasks


@router.post(
    "/shipments/{shipment_id}/finalize-manifest",
    status_code=status.HTTP_200_OK,
    response_model=FinalizeManifestResponse,
    summary="Finalize cargo manifest",
    description=(
        "Declares the cargo of a draft shipment and moves it to "
        "`ReadyForManifest`. The total weight must be greater than zero. A "
        "`ShipmentManifestFinalized` event is written to the module outbox in "
        "the same transaction, and published by `dispatch-messages`."
    ),
    responses={
        404: {
            "description": "No shipment matches the identifier.",
            "content": {"application/problem+json": {}},
        },
        409: {
            "description": "The shipment is no longer a draft.",
            "content": {"application/problem+json": {}},
        },
        422: {
            "description": "The manifest violates a domain invariant.",
            "content": {"application/problem+json": {}},
        },
    },
)
async def finalize_manifest(
    shipment_id: Annotated[
        str, Path(description="Identifier of the shipment to declare.")
    ],
    command: FinalizeManifestCommand,
    handler: Annotated[FinalizeManifestHandler, Depends(get_finalize_manifest_handler)],
) -> FinalizeManifestResponse:
    """Handle ``POST /shipments/{shipment_id}/finalize-manifest``."""
    shipment = await handler.handle(shipment_id, command)
    manifest = shipment.manifest

    return FinalizeManifestResponse(
        shipment_id=str(shipment.id),
        waybill_number=str(shipment.waybill_number),
        status=shipment.status,
        manifest=ManifestView(
            total_weight_kg=manifest.total_weight_kg,
            total_volume_cbm=manifest.total_volume_cbm,
            commodity_code=manifest.commodity_code,
        ),
        links=_next_tasks(shipment),
    )
