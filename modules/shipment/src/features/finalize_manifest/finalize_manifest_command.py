"""Command DTO of the *finalize cargo manifest* slice."""

from pydantic import BaseModel, ConfigDict, Field


class FinalizeManifestCommand(BaseModel):
    """Intent to declare the cargo of an existing draft shipment.

    The figures are only type-checked here. "Weight greater than zero" is a
    domain rule of the aggregate, not a shape rule of the payload, so it is
    enforced there and surfaces as an invariant violation.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "total_weight_kg": 12500.5,
                    "total_volume_cbm": 68.25,
                    "commodity_code": "8471",
                }
            ]
        },
    )

    total_weight_kg: float = Field(
        description="Gross weight of the cargo, in kilograms.",
    )
    total_volume_cbm: float = Field(
        description="Gross volume of the cargo, in cubic metres.",
    )
    commodity_code: str = Field(
        min_length=1,
        max_length=16,
        description="Customs classification of the goods (HS code).",
    )
