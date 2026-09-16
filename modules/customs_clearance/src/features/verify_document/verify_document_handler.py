"""Command handler of the *verify document* slice."""

import logging
from uuid import UUID

from modules.customs_clearance.src.domain.clearance_case import ClearanceCase
from modules.customs_clearance.src.domain.entities import DocumentRegistryItem
from modules.customs_clearance.src.domain.exceptions import (
    ClearanceCaseNotFoundError,
    DocumentNotFoundError,
)
from modules.customs_clearance.src.domain.repositories import ClearanceCaseRepository
from modules.customs_clearance.src.domain.value_objects import CaseId
from modules.customs_clearance.src.features.verify_document.verify_document_command import (  # noqa: E501
    VerifyDocumentCommand,
)
from modules.shared.message_bus import OutboxMessageRepository

logger = logging.getLogger(__name__)


class VerifyDocumentHandler:
    """Clears a document and announces a case whose paperwork is complete.

    The aggregate decides whether the sign-off finished the verification stage;
    this handler only carries the answer to the outbox. The updated case and
    the ``DocumentVerificationCompleted`` row are written through the same
    session, so the request commits them together: the risk assessment is never
    announced for a verification that rolled back, and a completed
    verification never fails to announce itself.
    """

    def __init__(
        self,
        clearance_cases: ClearanceCaseRepository,
        outbox: OutboxMessageRepository,
    ) -> None:
        self._clearance_cases = clearance_cases
        self._outbox = outbox

    async def handle(
        self,
        case_id: str,
        document_id: UUID,
        command: VerifyDocumentCommand,
    ) -> tuple[ClearanceCase, DocumentRegistryItem]:
        """Clear the document and queue the event when one is raised."""
        identity = CaseId(case_id)

        clearance_case = await self._clearance_cases.find_by_id(identity)
        if clearance_case is None:
            raise ClearanceCaseNotFoundError(
                f"No clearance case matches the identifier '{case_id}'."
            )

        event = clearance_case.verify_document(
            document_id=document_id,
            inspector_id=command.inspector_id,
        )

        await self._clearance_cases.persist(clearance_case)

        if event is not None:
            await self._outbox.schedule(event)
            logger.info(
                "Case %s has complete paperwork; risk assessment queued.",
                clearance_case.id,
            )

        # Read back from the aggregate: verify_document works through the
        # collection, so this is the instance it just changed. It cannot be
        # missing here - verify_document raises when it is - but saying so out
        # loud beats an assertion that disappears under -O.
        document = clearance_case.find_document(document_id)
        if document is None:  # pragma: no cover - unreachable
            raise DocumentNotFoundError(
                f"No document matches the identifier '{document_id}' on case {case_id}."
            )

        return clearance_case, document
