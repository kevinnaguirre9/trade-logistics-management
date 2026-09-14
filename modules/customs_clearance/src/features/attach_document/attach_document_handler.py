"""Command handler of the *attach legal document reference* slice."""

from modules.customs_clearance.src.domain.clearance_case import ClearanceCase
from modules.customs_clearance.src.domain.entities import DocumentRegistryItem
from modules.customs_clearance.src.domain.exceptions import (
    ClearanceCaseNotFoundError,
)
from modules.customs_clearance.src.domain.repositories import ClearanceCaseRepository
from modules.customs_clearance.src.domain.value_objects import CaseId
from modules.customs_clearance.src.features.attach_document.attach_document_command import (  # noqa: E501
    AttachDocumentCommand,
)


class AttachDocumentHandler:
    """Files a document against a case and saves the whole aggregate.

    The document and the case status change together - attaching the first one
    moves the case to ``DocumentVerification`` - so they are persisted through
    the same session and commit as one.
    """

    def __init__(self, clearance_cases: ClearanceCaseRepository) -> None:
        self._clearance_cases = clearance_cases

    async def handle(
        self,
        case_id: str,
        command: AttachDocumentCommand,
    ) -> tuple[ClearanceCase, DocumentRegistryItem]:
        """Attach the document and return the case alongside it.

        Both are returned because the caller needs the new document's
        identifier as well as the state the case is now in.
        """
        identity = CaseId(case_id)

        clearance_case = await self._clearance_cases.find_by_id(identity)
        if clearance_case is None:
            raise ClearanceCaseNotFoundError(
                f"No clearance case matches the identifier '{case_id}'."
            )

        document = clearance_case.attach_document(
            document_type=command.document_type,
            file_uuid=command.file_uuid,
        )

        await self._clearance_cases.persist(clearance_case)

        return clearance_case, document
