"""ClearanceCase aggregate root."""

from modules.customs_clearance.src.domain.enums import AssessmentStatus
from modules.customs_clearance.src.domain.exceptions import (
    InvalidShipmentReferenceError,
)
from modules.customs_clearance.src.domain.value_objects import CaseId, Money


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
    ) -> None:
        self.id = case_id
        self.shipment_id = shipment_id
        self.status = status
        self.declaration_value = declaration_value
        self.duty_fee = duty_fee

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
