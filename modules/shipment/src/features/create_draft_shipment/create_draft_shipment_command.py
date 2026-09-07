"""Command DTO of the *create draft shipment* slice."""

from pydantic import BaseModel, ConfigDict, Field


class CreateDraftShipmentCommand(BaseModel):
    """Intent to open a new shipment between two ports.

    The public contract is snake_case (``origin_port_code``), matching the
    Python field names, per PEP 8.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {"origin_port_code": "ESVLC", "destination_port_code": "USNYC"}
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
