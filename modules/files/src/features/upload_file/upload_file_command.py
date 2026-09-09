"""Command DTO of the *upload file* slice."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FileReferenceInput(BaseModel):
    """One thing the uploaded file is about.

    ``context`` and ``entity_type`` say what the file relates to and are
    required. The two identifying fields are not: a reference can describe an
    external entity that has files but no identifier here, so ``entity_id`` and
    ``uuid`` are each optional.

    There is no ``id`` here on purpose. ``id`` belongs to the reference record
    itself and is assigned by the database, so a client that sends one is
    refused rather than quietly ignored.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    context: str = Field(
        min_length=1,
        max_length=128,
        description="Bounded context the file relates to, e.g. 'customs'.",
    )
    entity_type: str = Field(
        min_length=1,
        max_length=128,
        description="Kind of thing the file is about, e.g. 'ClearanceCase'.",
    )
    entity_id: int | str | None = Field(
        default=None,
        description="Primary key of that entity, when it has one.",
    )
    uuid: UUID | None = Field(
        default=None,
        description="UUID of that entity, when it has one.",
    )


class UploadFileCommand(BaseModel):
    """Intent to store one file on one disk, related to zero or more owners.

    Only the shape is checked here. Where a file may be written, and how big it
    may be, are rules of the domain and of the deployment, so they are enforced
    by the storage location value object and by the storage port.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "disk": "local",
                    "path": "customs/clearance-cases",
                    "name": "commercial_invoice.pdf",
                    "metadata": {"issued_by": "ACME Freight"},
                    "references": [
                        {
                            "context": "customs",
                            "entity_type": "ClearanceCase",
                            "entity_id": 1,
                            "uuid": "123e4567-e89b-12d3-a456-426614174000",
                        }
                    ],
                }
            ]
        },
    )

    disk: str = Field(
        min_length=1,
        max_length=32,
        description="Storage class to write to: 'local', 'gcp', 'aws', 'sftp'.",
    )
    path: str = Field(
        default="",
        max_length=512,
        description="Directory the file is saved under, relative to the disk.",
    )
    name: str = Field(
        min_length=1,
        max_length=255,
        description="Original file name, extension included.",
    )
    content_type: str | None = Field(
        default=None,
        max_length=255,
        description="Media type of the upload; taken from the part when absent.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque JSON the caller wants stored alongside the file.",
    )
    references: list[FileReferenceInput] = Field(
        default_factory=list,
        description="Aggregates in other bounded contexts that own this file.",
    )
