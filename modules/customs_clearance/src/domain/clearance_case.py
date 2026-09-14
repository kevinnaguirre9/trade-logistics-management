"""ClearanceCase aggregate root."""

from uuid import UUID

from modules.customs_clearance.src.domain.entities import DocumentRegistryItem
from modules.customs_clearance.src.domain.enums import AssessmentStatus, DocumentType
from modules.customs_clearance.src.domain.exceptions import (
    DocumentAlreadyAttachedError,
    DocumentsNotAttachableError,
    InvalidShipmentReferenceError,
)
from modules.customs_clearance.src.domain.value_objects import CaseId, Money

#: Once customs has decided, the paperwork is closed: nothing further can be
#: filed against the case in either direction.
DECIDED_STATUSES = frozenset(
    {
        AssessmentStatus.RELEASED,
        AssessmentStatus.REJECTED,
    }
)


class ClearanceCase:
    """Regulatory compliance state machine for one shipment.

    Pure Python: persistence is attached from the infrastructure layer through
    imperative mapping, so this class knows nothing about SQLAlchemy.

    ``shipment_id`` is deliberately a plain string. The shipment lives in
    another bounded context, so this module holds its identifier and nothing
    else: no object reference, no foreign key, no shared table.
    """

    def __init__(
        self,
        case_id: CaseId,
        shipment_id: str,
        status: AssessmentStatus,
        declaration_value: Money | None = None,
        duty_fee: Money | None = None,
        documents: list[DocumentRegistryItem] | None = None,
    ) -> None:
        self.id = case_id
        self.shipment_id = shipment_id
        self.status = status
        self.declaration_value = declaration_value
        self.duty_fee = duty_fee
        self.documents = documents if documents is not None else []

    @classmethod
    def open_for_shipment(cls, case_id: CaseId, shipment_id: str) -> "ClearanceCase":
        """Start tracking a shipment through customs.

        The case opens knowing only which shipment it belongs to: the declared
        value arrives with the documents, and the duty fee is computed later by
        the risk assessment.
        """
        return cls(
            case_id=case_id,
            shipment_id=cls._validated_shipment_id(shipment_id),
            status=AssessmentStatus.OPENED,
        )

    def attach_document(
        self,
        document_type: DocumentType | str,
        file_uuid: UUID | str,
    ) -> DocumentRegistryItem:
        """Register an uploaded file as one of the case's legal documents.

        Filing the first document is what starts the verification stage: a case
        sitting at ``Opened`` has nothing for an inspector to look at, so the
        arrival of paperwork is the transition, not a separate command.

        Returns the registered item, because the caller needs its identifier to
        point an inspector at it.
        """
        if self.status in DECIDED_STATUSES:
            raise DocumentsNotAttachableError(
                f"Case {self.id} is already {self.status}; its paperwork is closed."
            )

        document = DocumentRegistryItem.attach(
            document_type=document_type,
            file_uuid=file_uuid,
        )

        if self.holds_file(document.file_uuid):
            raise DocumentAlreadyAttachedError(
                f"File {document.file_uuid} is already attached to case {self.id}."
            )

        self.documents.append(document)

        if self.status is AssessmentStatus.OPENED:
            self.status = AssessmentStatus.DOCUMENT_VERIFICATION

        return document

    def holds_file(self, file_uuid: UUID) -> bool:
        """Return ``True`` when that stored file is already on the case."""
        return any(document.file_uuid == file_uuid for document in self.documents)

    def find_document(self, document_id: UUID) -> DocumentRegistryItem | None:
        """Return one of the case's documents by its identifier."""
        return next(
            (document for document in self.documents if document.id == document_id),
            None,
        )

    @staticmethod
    def _validated_shipment_id(value: object) -> str:
        """Return the shipment reference or raise."""
        if not isinstance(value, str):
            raise InvalidShipmentReferenceError(
                "The shipment reference must be a string."
            )

        reference = value.strip()
        if not reference:
            raise InvalidShipmentReferenceError("The shipment reference is required.")
        return reference

    def __repr__(self) -> str:
        """Return a debugging representation of the aggregate."""
        return (
            f"ClearanceCase(id={self.id}, shipment_id={self.shipment_id}, "
            f"status={self.status})"
        )
