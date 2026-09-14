"""HTTP controller of the *attach legal document reference* slice.

``POST /customs/cases/{case_id}/documents``
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from modules.customs_clearance.src.domain.clearance_case import ClearanceCase
from modules.customs_clearance.src.domain.entities import DocumentRegistryItem
from modules.customs_clearance.src.domain.enums import AssessmentStatus, DocumentType
from modules.customs_clearance.src.features.attach_document.attach_document_command import (  # noqa: E501
    AttachDocumentCommand,
)
from modules.customs_clearance.src.features.attach_document.attach_document_handler import (  # noqa: E501
    AttachDocumentHandler,
)
from modules.customs_clearance.src.infrastructure.repositories import (
    PostgresClearanceCaseRepository,
)
from modules.shared.database import get_session
from modules.shared.http.hateoas import HypermediaResponse, Link

router = APIRouter()


class DocumentView(BaseModel):
    """Read model of one document filed against the case."""

    document_id: UUID = Field(description="Identifier of the registry entry.")
    document_type: DocumentType = Field(description="Kind of legal document.")
    file_uuid: UUID = Field(description="Stored file this entry points at.")
    is_verified: bool = Field(description="Whether an inspector has cleared it.")
    verified_by_inspector_id: str | None = Field(
        description="Inspector who cleared it, once one has.",
    )


class AttachDocumentResponse(HypermediaResponse):
    """The case after the document was filed, plus the tasks allowed next."""

    model_config = ConfigDict(populate_by_name=True)

    case_id: str = Field(description="Identifier of the clearance case.")
    shipment_id: str = Field(description="Shipment the case is tracking.")
    status: AssessmentStatus = Field(description="Assessment status of the case.")
    document: DocumentView = Field(description="The document just filed.")
    documents_attached: int = Field(
        description="How many documents the case now holds.",
    )


async def get_attach_document_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AttachDocumentHandler:
    """Build the handler with its PostgreSQL-backed repository."""
    return AttachDocumentHandler(
        clearance_cases=PostgresClearanceCaseRepository(session)
    )


def _next_tasks(
    clearance_case: ClearanceCase,
    document: DocumentRegistryItem,
) -> list[Link]:
    """Return the tasks allowed on the case in its current state."""
    case_id = str(clearance_case.id)

    # Reaching this point means the paperwork was open, so it still is: a case
    # closes on a decision, and filing a document is not one. Both tasks are
    # therefore always available here.
    return [
        Link(
            rel="verify-document",
            href=f"/customs/cases/{case_id}/documents/{document.id}/verify",
            method="POST",
        ),
        Link(
            rel="attach-document",
            href=f"/customs/cases/{case_id}/documents",
            method="POST",
        ),
    ]


@router.post(
    "/customs/cases/{case_id}/documents",
    status_code=status.HTTP_201_CREATED,
    response_model=AttachDocumentResponse,
    summary="Attach legal document reference",
    description=(
        "Files an uploaded document against a clearance case. `file_uuid` is "
        "the identifier returned by `POST /files`; customs stores it by value "
        "and never resolves it. The first document moves a case from `Opened` "
        "to `DocumentVerification`."
    ),
    responses={
        404: {
            "description": "No clearance case matches the identifier.",
            "content": {"application/problem+json": {}},
        },
        409: {
            "description": (
                "The case has been decided, or that file is already attached."
            ),
            "content": {"application/problem+json": {}},
        },
        422: {
            "description": "The payload violates a domain invariant.",
            "content": {"application/problem+json": {}},
        },
    },
)
async def attach_document(
    case_id: Annotated[
        str, Path(description="Identifier of the clearance case to file against.")
    ],
    command: AttachDocumentCommand,
    handler: Annotated[AttachDocumentHandler, Depends(get_attach_document_handler)],
) -> AttachDocumentResponse:
    """Handle ``POST /customs/cases/{case_id}/documents``."""
    clearance_case, document = await handler.handle(case_id, command)

    return AttachDocumentResponse(
        case_id=str(clearance_case.id),
        shipment_id=clearance_case.shipment_id,
        status=clearance_case.status,
        document=DocumentView(
            document_id=document.id,
            document_type=document.document_type,
            file_uuid=document.file_uuid,
            is_verified=document.is_verified,
            verified_by_inspector_id=document.verified_by_inspector_id,
        ),
        documents_attached=len(clearance_case.documents),
        links=_next_tasks(clearance_case, document),
    )
