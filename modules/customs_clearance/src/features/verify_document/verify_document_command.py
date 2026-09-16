"""Command DTO of the *verify document* slice."""

from pydantic import BaseModel, ConfigDict, Field

from modules.customs_clearance.src.domain.entities import MAX_INSPECTOR_ID_LENGTH


class VerifyDocumentCommand(BaseModel):
    """Intent of a customs inspector to clear one filed document.

    Only the shape is checked here. Whether that document can still be cleared
    at all is a rule of the aggregate, not of the payload.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"examples": [{"inspector_id": "INSP-4471"}]},
    )

    inspector_id: str = Field(
        min_length=1,
        max_length=MAX_INSPECTOR_ID_LENGTH,
        description="Identifier of the customs inspector signing the document off.",
    )
