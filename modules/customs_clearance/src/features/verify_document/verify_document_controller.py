"""HTTP controller of the *verify document* slice.

``POST /customs/cases/{case_id}/documents/{document_id}/verify``
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from modules.customs_clearance.src.domain.clearance_case import (
    DECIDED_STATUSES,
    ClearanceCase,
)
from modules.customs_clearance.src.domain.entities import DocumentRegistryItem
from modules.customs_clearance.src.domain.enums import AssessmentStatus, DocumentType
from modules.customs_clearance.src.features.verify_document.verify_document_command import (  # noqa: E501
    VerifyDocumentCommand,
)
from modules.customs_clearance.src.features.verify_document.verify_document_handler import (  # noqa: E501
    VerifyDocumentHandler,
)
from modules.customs_clearance.src.infrastructure.database import SCHEMA
from modules.customs_clearance.src.infrastructure.repositories import (
    PostgresClearanceCaseRepository,
)
from modules.shared.database import get_session
from modules.shared.http.hateoas import HypermediaResponse, Link
from modules.shared.message_bus import OutboxMessageRepository
from modules.shared.message_bus.session import bind_module_schema

router = APIRouter()


class VerifiedDocumentView(BaseModel):
    """Read model of the document the inspector just cleared."""

    document_id: UUID = Field(description="Identifier of the registry entry.")
    document_type: DocumentType = Field(description="Kind of legal document.")
    file_uuid: UUID = Field(description="Stored file this entry points at.")
    is_verified: bool = Field(description="Always true once this call succeeds.")
    verified_by_inspector_id: str = Field(description="Inspector who cleared it.")


class VerifyDocumentResponse(HypermediaResponse):
    """The case after the sign-off, plus the tasks allowed next."""

    model_config = ConfigDict(populate_by_name=True)

    case_id: str = Field(description="Identifier of the clearance case.")
    shipment_id: str = Field(description="Shipment the case is tracking.")
    status: AssessmentStatus = Field(description="Assessment status of the case.")
    document: VerifiedDocumentView = Field(description="The document just cleared.")
    documents_verified: int = Field(
        description="How many of the case's documents are now cleared.",
    )
    paperwork_complete: bool = Field(
        description=(
            "Whether every required kind of document is cleared. When this "
            "turns true the case moves to `RiskAssessment` and a "
            "`DocumentVerificationCompleted` event is queued in the outbox."
        ),
    )


async def get_verify_document_handler(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VerifyDocumentHandler:
    """Build the handler with its PostgreSQL-backed collaborators.

    The session is bound to this module schema first: the outbox table is
    declared without one, so the write has to be told which module it belongs
    to before the request touches the database.
    """
    await bind_module_schema(session, SCHEMA)

    return VerifyDocumentHandler(
        clearance_cases=PostgresClearanceCaseRepository(session),
        outbox=OutboxMessageRepository(session),
    )


def _next_tasks(clearance_case: ClearanceCase) -> list[Link]:
    """Return the tasks allowed on the case in its current state."""
    case_id = str(clearance_case.id)

    if clearance_case.status in DECIDED_STATUSES:
        return []

    # While paperwork is still outstanding the inspector's work continues; once
    # it is complete the risk assessment has been queued and nothing further is
    # asked of the caller here.
    if clearance_case.status is AssessmentStatus.DOCUMENT_VERIFICATION:
        return [
            Link(
                rel="attach-document",
                href=f"/customs/cases/{case_id}/documents",
                method="POST",
            )
        ]

    return []


@router.post(
    "/customs/cases/{case_id}/documents/{document_id}/verify",
    status_code=status.HTTP_200_OK,
    response_model=VerifyDocumentResponse,
    summary="Verify document",
    description=(
        "Records a customs inspector's sign-off on one filed document. When "
        "the sign-off leaves every required kind of document cleared, the case "
        "moves to `RiskAssessment` and a `DocumentVerificationCompleted` event "
        "is written to the module outbox in the same transaction, to be "
        "published by `dispatch-messages`."
    ),
    responses={
        404: {
            "description": "No such clearance case, or no such document on it.",
            "content": {"application/problem+json": {}},
        },
        409: {
            "description": (
                "The case has been decided, or the document is already cleared."
            ),
            "content": {"application/problem+json": {}},
        },
        422: {
            "description": "The payload violates a domain invariant.",
            "content": {"application/problem+json": {}},
        },
    },
)
async def verify_document(
    case_id: Annotated[str, Path(description="Identifier of the clearance case.")],
    document_id: Annotated[UUID, Path(description="Identifier of the document.")],
    command: VerifyDocumentCommand,
    handler: Annotated[VerifyDocumentHandler, Depends(get_verify_document_handler)],
) -> VerifyDocumentResponse:
    """Handle ``POST /customs/cases/{case_id}/documents/{document_id}/verify``."""
    clearance_case, document = await handler.handle(case_id, document_id, command)

    return VerifyDocumentResponse(
        case_id=str(clearance_case.id),
        shipment_id=clearance_case.shipment_id,
        status=clearance_case.status,
        document=_as_view(document),
        documents_verified=sum(
            1 for item in clearance_case.documents if item.is_verified
        ),
        paperwork_complete=clearance_case.has_complete_paperwork(),
        links=_next_tasks(clearance_case),
    )


def _as_view(document: DocumentRegistryItem) -> VerifiedDocumentView:
    """Render the cleared document."""
    return VerifiedDocumentView(
        document_id=document.id,
        document_type=document.document_type,
        file_uuid=document.file_uuid,
        is_verified=document.is_verified,
        verified_by_inspector_id=document.verified_by_inspector_id or "",
    )
