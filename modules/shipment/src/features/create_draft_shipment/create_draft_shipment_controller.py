"""HTTP controller of the *create draft shipment* slice: ``POST /shipments``."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from modules.shared.database import get_session
from modules.shared.http.hateoas import HypermediaResponse, Link
from modules.shipment.src.domain.enums import TrackingStatus
from modules.shipment.src.features.create_draft_shipment.create_draft_shipment_command import (  # noqa: E501
    CreateDraftShipmentCommand,
)
from modules.shipment.src.features.create_draft_shipment.create_draft_shipment_handler import (  # noqa: E501
    CreateDraftShipmentHandler,
)
from modules.shipment.src.infrastructure.database.postgres_waybill_number_generator import (  # noqa: E501
    PostgresWaybillNumberGenerator,
)
from modules.shipment.src.infrastructure.repositories import (
    PostgresShipmentRepository,
)

router = APIRouter()


class CreateDraftShipmentResponse(HypermediaResponse):
    """Identity of the new draft plus the tasks it now allows."""

    model_config = ConfigDict(populate_by_name=True)

    shipment_id: str = Field(description="Identifier of the new shipment.")
    waybill_number: str = Field(description="Generated carrier tracking number.")
    status: TrackingStatus = Field(description="Lifecycle status of the shipment.")


async def get_create_draft_shipment_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CreateDraftShipmentHandler:
    """Build the handler with its PostgreSQL-backed collaborators."""
    return CreateDraftShipmentHandler(
        shipments=PostgresShipmentRepository(session),
        waybill_numbers=PostgresWaybillNumberGenerator(session),
    )


def _next_tasks(shipment_id: str) -> list[Link]:
    """Return the tasks that can be performed on a freshly created draft."""
    return [
        Link(
            rel="assign-route",
            href=f"/shipments/{shipment_id}/route",
            method="PUT",
        ),
        Link(
            rel="finalize-manifest",
            href=f"/shipments/{shipment_id}/finalize-manifest",
            method="POST",
        ),
    ]


@router.post(
    "/shipments",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateDraftShipmentResponse,
    summary="Create draft shipment",
    description=(
        "Opens a shipment in `Draft` state and assigns it a unique waybill "
        "number. The response links to the tasks allowed next."
    ),
    responses={
        422: {
            "description": "The route violates a domain invariant.",
            "content": {"application/problem+json": {}},
        }
    },
)
async def create_draft_shipment(
    command: CreateDraftShipmentCommand,
    handler: Annotated[
        CreateDraftShipmentHandler, Depends(get_create_draft_shipment_handler)
    ],
) -> CreateDraftShipmentResponse:
    """Handle ``POST /shipments``."""
    shipment = await handler.handle(command)

    return CreateDraftShipmentResponse(
        shipment_id=str(shipment.id),
        waybill_number=str(shipment.waybill_number),
        status=shipment.status,
        links=_next_tasks(str(shipment.id)),
    )
