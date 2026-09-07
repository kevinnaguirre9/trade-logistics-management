"""HTTP controller of the *assign complex route* slice.

``PUT /shipments/{shipment_id}/route``
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from modules.shared.database import get_session
from modules.shared.http.hateoas import HypermediaResponse, Link
from modules.shipment.src.domain.enums import TrackingStatus
from modules.shipment.src.domain.shipment import Shipment
from modules.shipment.src.features.assign_route.assign_route_command import (
    AssignRouteCommand,
)
from modules.shipment.src.features.assign_route.assign_route_handler import (
    AssignRouteHandler,
)
from modules.shipment.src.infrastructure.repositories import (
    PostgresShipmentRepository,
)

router = APIRouter()


class RouteView(BaseModel):
    """Read model of the itinerary now planned for the shipment."""

    origin_port_code: str = Field(description="Port where the cargo is loaded.")
    destination_port_code: str = Field(description="Port of delivery.")
    transit_legs: list[str] = Field(description="Ordered intermediate calls.")


class AssignRouteResponse(HypermediaResponse):
    """The shipment after the route was redrawn, plus the tasks allowed next."""

    model_config = ConfigDict(populate_by_name=True)

    shipment_id: str = Field(description="Identifier of the shipment.")
    waybill_number: str = Field(description="Carrier tracking number.")
    status: TrackingStatus = Field(description="Lifecycle status of the shipment.")
    route: RouteView = Field(description="Itinerary currently planned.")


async def get_assign_route_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AssignRouteHandler:
    """Build the handler with its PostgreSQL-backed repository."""
    return AssignRouteHandler(shipments=PostgresShipmentRepository(session))


def _next_tasks(shipment: Shipment) -> list[Link]:
    """Return the tasks allowed on the shipment in its current state."""
    shipment_id = str(shipment.id)

    # Reaching this point means the route was modifiable, so it still is.
    tasks = [
        Link(
            rel="assign-route",
            href=f"/shipments/{shipment_id}/route",
            method="PUT",
        )
    ]

    # The manifest can only be finalized while the shipment is a draft.
    if shipment.status is TrackingStatus.DRAFT:
        tasks.append(
            Link(
                rel="finalize-manifest",
                href=f"/shipments/{shipment_id}/finalize-manifest",
                method="POST",
            )
        )

    return tasks


@router.put(
    "/shipments/{shipment_id}/route",
    status_code=status.HTTP_200_OK,
    response_model=AssignRouteResponse,
    summary="Assign complex route",
    description=(
        "Replaces the itinerary of a shipment. `transit_legs` lists the "
        "intermediate calls only, in order; together with the endpoints they "
        "must form a logical sequence that never calls at the same port twice. "
        "The route is frozen once the shipment awaits customs release, is in "
        "transit or has been delivered."
    ),
    responses={
        404: {
            "description": "No shipment matches the identifier.",
            "content": {"application/problem+json": {}},
        },
        409: {
            "description": "The shipment has advanced past a modifiable route.",
            "content": {"application/problem+json": {}},
        },
        422: {
            "description": "The route violates a domain invariant.",
            "content": {"application/problem+json": {}},
        },
    },
)
async def assign_route(
    shipment_id: Annotated[
        str, Path(description="Identifier of the shipment to reroute.")
    ],
    command: AssignRouteCommand,
    handler: Annotated[AssignRouteHandler, Depends(get_assign_route_handler)],
) -> AssignRouteResponse:
    """Handle ``PUT /shipments/{shipment_id}/route``."""
    shipment = await handler.handle(shipment_id, command)

    return AssignRouteResponse(
        shipment_id=str(shipment.id),
        waybill_number=str(shipment.waybill_number),
        status=shipment.status,
        route=RouteView(
            origin_port_code=shipment.route.origin_port_code,
            destination_port_code=shipment.route.destination_port_code,
            transit_legs=list(shipment.route.transit_legs),
        ),
        links=_next_tasks(shipment),
    )
