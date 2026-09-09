"""HTTP controller of the *upload file* slice.

``POST /files`` (multipart/form-data)

The request carries bytes as well as JSON, so it arrives as a multipart form
rather than a JSON body: ``file`` is the upload itself and ``metadata`` and
``references`` are JSON documents in their own parts. Every other field is a
plain form value, named exactly as the JSON contract names it.
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from modules.files.src.domain.exceptions import InvalidUploadPayloadError
from modules.files.src.domain.services import FileStorage
from modules.files.src.domain.stored_file import StoredFile
from modules.files.src.features.upload_file.upload_file_command import (
    UploadFileCommand,
)
from modules.files.src.features.upload_file.upload_file_handler import (
    UploadFileHandler,
)
from modules.files.src.infrastructure.repositories import (
    PostgresStoredFileRepository,
)
from modules.files.src.infrastructure.storage.provider import get_file_storage
from modules.shared.config import get_settings
from modules.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter()

#: Bytes read from the upload per iteration.
CHUNK_SIZE = 64 * 1024


class FileReferenceView(BaseModel):
    """Read model of one thing the file is about."""

    id: int | None = Field(
        description="Key of this reference record, assigned by the database.",
    )
    context: str = Field(description="Bounded context the file relates to.")
    entity_type: str = Field(description="Kind of thing the file is about.")
    entity_id: str | None = Field(
        description="Primary key of that entity, when it has one.",
    )
    entity_uuid: UUID | None = Field(
        description="UUID of that entity, when it has one.",
    )


class UploadFileResponse(BaseModel):
    """The file as it is now stored.

    ``file_uuid`` is what the calling context keeps: customs, for instance,
    stores it on a clearance case document and never holds the bytes itself.
    """

    file_uuid: UUID = Field(description="Identifier of the stored file.")
    disk: str = Field(description="Storage class holding the bytes.")
    path: str = Field(description="Directory the file was saved under.")
    name: str = Field(description="Original file name.")
    key: str = Field(description="Object key of the file on its disk.")
    size_bytes: int = Field(description="Size of what was actually written.")
    content_type: str = Field(description="Media type of the stored file.")
    checksum: str = Field(description="Digest of the stored bytes, 'sha256:<hex>'.")
    metadata: dict[str, Any] = Field(description="Metadata supplied by the caller.")
    references: list[FileReferenceView] = Field(
        description="What this file is about, in other bounded contexts.",
    )


async def get_upload_file_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> UploadFileHandler:
    """Build the handler with its PostgreSQL and storage collaborators."""
    return UploadFileHandler(
        files=PostgresStoredFileRepository(session),
        storage=storage,
    )


def _parse_json_part(raw: str | None, part: str, fallback: Any) -> Any:
    """Return a JSON part of the form, or say which part was malformed."""
    if raw is None or not raw.strip():
        return fallback

    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise InvalidUploadPayloadError(
            f"The '{part}' part is not valid JSON: {error.msg}."
        ) from error


async def _chunks(upload: UploadFile) -> AsyncIterator[bytes]:
    """Yield the upload in fixed-size chunks, so it is never held whole."""
    while chunk := await upload.read(CHUNK_SIZE):
        yield chunk


@router.post(
    "/files",
    status_code=status.HTTP_201_CREATED,
    response_model=UploadFileResponse,
    summary="Upload file",
    description=(
        "Stores a file on one of the configured disks and records what it is "
        "about. The response carries the `file_uuid` other bounded contexts "
        "hold on to. `metadata` and `references` are JSON documents sent as "
        "their own form parts, and `references` is optional: the client "
        "decides whether the file relates to anything."
    ),
    responses={
        409: {
            "description": "Something is already stored at that location.",
            "content": {"application/problem+json": {}},
        },
        413: {
            "description": "The upload exceeds the configured maximum size.",
            "content": {"application/problem+json": {}},
        },
        422: {
            "description": "The request violates a domain invariant.",
            "content": {"application/problem+json": {}},
        },
        503: {
            "description": "The disk's backend is unavailable.",
            "content": {"application/problem+json": {}},
        },
    },
)
async def upload_file(
    file: Annotated[UploadFile, File(description="The file being uploaded.")],
    handler: Annotated[UploadFileHandler, Depends(get_upload_file_handler)],
    disk: Annotated[
        str | None,
        Form(description="Disk to write to; the configured default when absent."),
    ] = None,
    path: Annotated[str, Form(description="Directory the file is saved under.")] = "",
    name: Annotated[
        str | None,
        Form(description="File name; the uploaded part's name when absent."),
    ] = None,
    metadata: Annotated[
        str | None, Form(description="JSON object stored alongside the file.")
    ] = None,
    references: Annotated[
        str | None,
        Form(description="Optional JSON array saying what the file is about."),
    ] = None,
) -> UploadFileResponse:
    """Handle ``POST /files``."""
    settings = get_settings()

    # The command is assembled here rather than bound by FastAPI, because the
    # JSON parts arrive as text inside a multipart form. Its validation errors
    # are re-raised as the framework's own, so a malformed reference reads
    # exactly like any other 422 instead of escaping as a 500.
    try:
        command = UploadFileCommand(
            disk=disk or settings.files_default_disk,
            path=path,
            name=name or file.filename or "",
            content_type=file.content_type,
            metadata=_parse_json_part(metadata, "metadata", {}),
            references=_parse_json_part(references, "references", []),
        )
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error

    stored_file = await handler.handle(command, _chunks(file))

    return _as_response(stored_file)


def _as_response(stored_file: StoredFile) -> UploadFileResponse:
    """Render the aggregate as the upload response."""
    return UploadFileResponse(
        file_uuid=stored_file.id.value,
        disk=stored_file.disk,
        path=stored_file.location.path,
        name=stored_file.location.name,
        key=stored_file.key,
        size_bytes=stored_file.size_bytes,
        content_type=stored_file.content_type,
        checksum=stored_file.checksum,
        metadata=stored_file.metadata,
        references=[
            FileReferenceView(
                id=reference.id,
                context=reference.context,
                entity_type=reference.entity_type,
                entity_id=reference.entity_id,
                entity_uuid=reference.entity_uuid,
            )
            for reference in stored_file.references
        ],
    )
