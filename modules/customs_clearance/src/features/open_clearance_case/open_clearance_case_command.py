"""Command DTO of the *open clearance case* slice."""

from pydantic import BaseModel, ConfigDict, Field


class OpenClearanceCaseCommand(BaseModel):
    """Intent to start tracking a shipment through customs.

    Built from the body of a ``ShipmentManifestFinalized`` message rather than
    from an HTTP payload, so validating it here is what stops a malformed
    message from reaching the domain.
    """

    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
        str_strip_whitespace=True,
    )

    shipment_id: str = Field(
        min_length=1,
        max_length=64,
        description="Identifier of the shipment the case is opened for.",
    )
    commodity_code: str = Field(
        min_length=1,
        max_length=16,
        description="Customs classification declared on the manifest.",
    )
