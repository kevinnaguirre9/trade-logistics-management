"""Command DTO of the *assign complex route* slice."""

from pydantic import BaseModel, ConfigDict, Field


class AssignRouteCommand(BaseModel):
    """Intent to redraw the itinerary of an existing shipment.

    The target shipment travels in the path, not in the body, so it is handed
    to the handler separately: the body carries the new route only.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "origin_port_code": "ESVLC",
                    "destination_port_code": "USNYC",
                    "transit_legs": ["MAMIR", "PTLIS"],
                }
            ]
        },
    )

    origin_port_code: str = Field(
        min_length=5,
        max_length=5,
        description="UN/LOCODE of the port where the cargo is loaded.",
    )
    destination_port_code: str = Field(
        min_length=5,
        max_length=5,
        description="UN/LOCODE of the port where the cargo is delivered.",
    )
    transit_legs: list[str] = Field(
        default_factory=list,
        description=(
            "Ordered intermediate calls between the origin and the "
            "destination. Endpoints are not repeated here."
        ),
    )
