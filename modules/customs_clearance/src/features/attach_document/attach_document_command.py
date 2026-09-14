"""Command DTO of the *attach legal document reference* slice."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.customs_clearance.src.domain.enums import DocumentType


class AttachDocumentCommand(BaseModel):
    """Intent to file one uploaded document against a clearance case.

    ``file_uuid`` is what the Files module answered with when the document was
    uploaded. Customs stores the value and never resolves it: the file could be
    on a local volume, in a bucket or on an SFTP server, and none of that is
    customs' business.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "document_type": "COMMERCIAL_INVOICE",
                    "file_uuid": "7c392d07-85d6-473e-b24f-6382c72cc648",
                }
            ]
        },
    )

    document_type: DocumentType = Field(
        description="Kind of legal document being filed.",
    )
    file_uuid: UUID = Field(
        description="Identifier of the stored file, as returned by POST /files.",
    )
