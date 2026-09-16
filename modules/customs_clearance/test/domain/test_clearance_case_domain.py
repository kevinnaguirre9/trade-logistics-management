"""Unit tests for the Customs Clearance domain model."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from modules.customs_clearance.src.domain.clearance_case import ClearanceCase
from modules.customs_clearance.src.domain.enums import AssessmentStatus, DocumentType
from modules.customs_clearance.src.domain.events import DocumentVerificationCompleted
from modules.customs_clearance.src.domain.exceptions import (
    CurrencyMismatchError,
    DocumentAlreadyAttachedError,
    DocumentAlreadyVerifiedError,
    DocumentNotFoundError,
    DocumentNotVerifiableError,
    DocumentsNotAttachableError,
    InvalidCaseIdError,
    InvalidDocumentReferenceError,
    InvalidInspectorError,
    InvalidMoneyError,
    InvalidShipmentReferenceError,
)
from modules.customs_clearance.src.domain.value_objects import CaseId, Money


class TestCaseId:
    def test_accepts_a_uuid(self) -> None:
        value = uuid4()

        assert CaseId(value).value == value

    def test_accepts_the_string_form(self) -> None:
        value = uuid4()

        assert CaseId(str(value)).value == value

    @pytest.mark.parametrize("value", ["not-a-uuid", "", 42, None])
    def test_rejects_anything_else(self, value: object) -> None:
        with pytest.raises(InvalidCaseIdError):
            CaseId(value)  # type: ignore[arg-type]

    def test_compares_by_value(self) -> None:
        value = uuid4()

        assert CaseId(value).equals(CaseId(value))
        assert not CaseId(value).equals(CaseId.generate())

    def test_exposes_its_column_value(self) -> None:
        value = uuid4()

        assert CaseId(value).__composite_values__() == (value,)

    def test_generates_a_unique_identity(self) -> None:
        assert isinstance(CaseId.generate().value, UUID)
        assert CaseId.generate() != CaseId.generate()


class TestMoney:
    def test_normalizes_the_currency(self) -> None:
        assert Money(Decimal("10"), " eur ").currency == "EUR"

    def test_rounds_to_the_minor_unit(self) -> None:
        assert Money(Decimal("10.005"), "EUR").amount == Decimal("10.01")
        assert Money(Decimal("10.004"), "EUR").amount == Decimal("10.00")

    def test_accepts_an_int_or_a_float(self) -> None:
        assert Money(10, "EUR").amount == Decimal("10.00")
        assert Money(10.10, "EUR").amount == Decimal("10.10")

    @pytest.mark.parametrize("currency", ["EU", "EURO", "12", "", None, 3])
    def test_rejects_an_invalid_currency(self, currency: object) -> None:
        with pytest.raises(InvalidMoneyError):
            Money(Decimal("1"), currency)  # type: ignore[arg-type]

    def test_rejects_a_negative_amount(self) -> None:
        with pytest.raises(InvalidMoneyError):
            Money(Decimal("-0.01"), "EUR")

    @pytest.mark.parametrize("amount", ["abc", None, True])
    def test_rejects_a_non_numeric_amount(self, amount: object) -> None:
        with pytest.raises(InvalidMoneyError):
            Money(amount, "EUR")  # type: ignore[arg-type]

    def test_adds_and_subtracts_within_one_currency(self) -> None:
        ten = Money(Decimal("10.00"), "EUR")
        two = Money(Decimal("2.50"), "EUR")

        assert ten.add(two) == Money(Decimal("12.50"), "EUR")
        assert ten.subtract(two) == Money(Decimal("7.50"), "EUR")

    @pytest.mark.parametrize("operation", ["add", "subtract", "covers"])
    def test_refuses_to_mix_currencies(self, operation: str) -> None:
        euros = Money(Decimal("10.00"), "EUR")
        dollars = Money(Decimal("10.00"), "USD")

        with pytest.raises(CurrencyMismatchError):
            getattr(euros, operation)(dollars)

    def test_knows_when_it_covers_another_amount(self) -> None:
        ten = Money(Decimal("10.00"), "EUR")

        assert ten.covers(Money(Decimal("10.00"), "EUR"))
        assert ten.covers(Money(Decimal("9.99"), "EUR"))
        assert not ten.covers(Money(Decimal("10.01"), "EUR"))

    def test_takes_a_percentage(self) -> None:
        assert Money(Decimal("200.00"), "EUR").percentage(10) == Money(
            Decimal("20.00"), "EUR"
        )

    def test_compares_by_value(self) -> None:
        assert Money(Decimal("10.00"), "EUR") == Money(Decimal("10"), "eur")

    def test_rebuilds_from_its_columns(self) -> None:
        assert Money.from_columns(Decimal("10.00"), "EUR") == Money(
            Decimal("10.00"), "EUR"
        )

    def test_answers_none_for_an_unset_amount(self) -> None:
        assert Money.from_columns(None, None) is None

    def test_exposes_its_column_values(self) -> None:
        assert Money(Decimal("10.00"), "EUR").__composite_values__() == (
            Decimal("10.00"),
            "EUR",
        )

    def test_reads_as_an_amount_and_a_currency(self) -> None:
        assert str(Money(Decimal("10.5"), "EUR")) == "10.50 EUR"


class TestOpenForShipment:
    def test_opens_the_case_in_the_opened_state(self) -> None:
        clearance_case = ClearanceCase.open_for_shipment(
            case_id=CaseId.generate(), shipment_id="s-1"
        )

        assert clearance_case.status is AssessmentStatus.OPENED
        assert clearance_case.shipment_id == "s-1"

    def test_leaves_the_money_undeclared(self) -> None:
        clearance_case = ClearanceCase.open_for_shipment(
            case_id=CaseId.generate(), shipment_id="s-1"
        )

        assert clearance_case.declaration_value is None
        assert clearance_case.duty_fee is None

    def test_trims_the_shipment_reference(self) -> None:
        clearance_case = ClearanceCase.open_for_shipment(
            case_id=CaseId.generate(), shipment_id="  s-1  "
        )

        assert clearance_case.shipment_id == "s-1"

    @pytest.mark.parametrize("shipment_id", ["", "   ", None, 42])
    def test_rejects_a_missing_shipment_reference(self, shipment_id: object) -> None:
        with pytest.raises(InvalidShipmentReferenceError):
            ClearanceCase.open_for_shipment(
                case_id=CaseId.generate(),
                shipment_id=shipment_id,  # type: ignore[arg-type]
            )

    def test_opens_with_no_paperwork_filed(self) -> None:
        clearance_case = ClearanceCase.open_for_shipment(
            case_id=CaseId.generate(), shipment_id="s-1"
        )

        assert clearance_case.documents == []


def a_case(status: AssessmentStatus = AssessmentStatus.OPENED) -> ClearanceCase:
    """Return a clearance case in the requested state."""
    clearance_case = ClearanceCase.open_for_shipment(
        case_id=CaseId.generate(), shipment_id="s-1"
    )
    clearance_case.status = status
    return clearance_case


class TestAttachDocument:
    def test_registers_the_file_under_its_type(self) -> None:
        clearance_case = a_case()
        file_uuid = uuid4()

        document = clearance_case.attach_document("COMMERCIAL_INVOICE", file_uuid)

        assert document.document_type is DocumentType.COMMERCIAL_INVOICE
        assert document.file_uuid == file_uuid
        assert clearance_case.documents == [document]

    def test_accepts_the_type_as_an_enum_member(self) -> None:
        document = a_case().attach_document(DocumentType.BILL_OF_LADING, uuid4())

        assert document.document_type is DocumentType.BILL_OF_LADING

    def test_accepts_the_file_reference_in_string_form(self) -> None:
        file_uuid = uuid4()

        document = a_case().attach_document("BILL_OF_LADING", str(file_uuid))

        assert document.file_uuid == file_uuid

    def test_files_every_document_unverified(self) -> None:
        document = a_case().attach_document("COMMERCIAL_INVOICE", uuid4())

        assert document.is_verified is False
        assert document.verified_by_inspector_id is None

    def test_starts_verification_when_the_first_document_arrives(self) -> None:
        clearance_case = a_case(AssessmentStatus.OPENED)

        clearance_case.attach_document("COMMERCIAL_INVOICE", uuid4())

        assert clearance_case.status is AssessmentStatus.DOCUMENT_VERIFICATION

    def test_leaves_the_status_alone_for_later_documents(self) -> None:
        clearance_case = a_case(AssessmentStatus.RISK_ASSESSMENT)

        clearance_case.attach_document("COMMERCIAL_INVOICE", uuid4())

        assert clearance_case.status is AssessmentStatus.RISK_ASSESSMENT

    def test_keeps_both_kinds_of_paperwork(self) -> None:
        clearance_case = a_case()

        clearance_case.attach_document("COMMERCIAL_INVOICE", uuid4())
        clearance_case.attach_document("BILL_OF_LADING", uuid4())

        assert len(clearance_case.documents) == 2

    def test_finds_a_document_by_its_identifier(self) -> None:
        clearance_case = a_case()
        document = clearance_case.attach_document("COMMERCIAL_INVOICE", uuid4())

        assert clearance_case.find_document(document.id) is document
        assert clearance_case.find_document(uuid4()) is None

    def test_refuses_the_same_file_twice(self) -> None:
        clearance_case = a_case()
        file_uuid = uuid4()
        clearance_case.attach_document("COMMERCIAL_INVOICE", file_uuid)

        with pytest.raises(DocumentAlreadyAttachedError):
            clearance_case.attach_document("BILL_OF_LADING", file_uuid)

        assert len(clearance_case.documents) == 1

    @pytest.mark.parametrize(
        "status", [AssessmentStatus.RELEASED, AssessmentStatus.REJECTED]
    )
    def test_refuses_to_file_against_a_decided_case(
        self, status: AssessmentStatus
    ) -> None:
        clearance_case = a_case(status)

        with pytest.raises(DocumentsNotAttachableError):
            clearance_case.attach_document("COMMERCIAL_INVOICE", uuid4())

        assert clearance_case.documents == []

    @pytest.mark.parametrize("document_type", ["PACKING_LIST", "", None, 7])
    def test_refuses_paperwork_customs_does_not_accept(
        self, document_type: object
    ) -> None:
        with pytest.raises(InvalidDocumentReferenceError):
            a_case().attach_document(document_type, uuid4())  # type: ignore[arg-type]

    @pytest.mark.parametrize("file_uuid", ["not-a-uuid", "", None, 7])
    def test_refuses_a_malformed_file_reference(self, file_uuid: object) -> None:
        with pytest.raises(InvalidDocumentReferenceError):
            a_case().attach_document(
                "COMMERCIAL_INVOICE",
                file_uuid,  # type: ignore[arg-type]
            )

    def test_knows_which_files_it_already_holds(self) -> None:
        clearance_case = a_case()
        file_uuid = uuid4()
        clearance_case.attach_document("COMMERCIAL_INVOICE", file_uuid)

        assert clearance_case.holds_file(file_uuid)
        assert not clearance_case.holds_file(uuid4())


def a_case_with_both_documents() -> ClearanceCase:
    """Return a case with one of each required document filed, none cleared."""
    clearance_case = a_case()
    clearance_case.attach_document("COMMERCIAL_INVOICE", uuid4())
    clearance_case.attach_document("BILL_OF_LADING", uuid4())
    return clearance_case


class TestVerifyDocument:
    def test_records_the_inspector_who_signed_it_off(self) -> None:
        clearance_case = a_case_with_both_documents()
        document = clearance_case.documents[0]

        clearance_case.verify_document(document.id, "INSP-4471")

        assert document.is_verified is True
        assert document.verified_by_inspector_id == "INSP-4471"

    def test_trims_the_inspector_identifier(self) -> None:
        clearance_case = a_case_with_both_documents()
        document = clearance_case.documents[0]

        clearance_case.verify_document(document.id, "  INSP-1  ")

        assert document.verified_by_inspector_id == "INSP-1"

    def test_raises_nothing_while_paperwork_is_outstanding(self) -> None:
        clearance_case = a_case_with_both_documents()

        event = clearance_case.verify_document(
            clearance_case.documents[0].id, "INSP-4471"
        )

        assert event is None
        assert clearance_case.status is AssessmentStatus.DOCUMENT_VERIFICATION

    def test_announces_completion_on_the_last_document(self) -> None:
        clearance_case = a_case_with_both_documents()
        clearance_case.verify_document(clearance_case.documents[0].id, "INSP-1")

        event = clearance_case.verify_document(clearance_case.documents[1].id, "INSP-2")

        assert isinstance(event, DocumentVerificationCompleted)
        assert event.case_id == str(clearance_case.id)
        assert event.shipment_id == clearance_case.shipment_id
        assert clearance_case.status is AssessmentStatus.RISK_ASSESSMENT

    def test_needs_one_of_every_required_kind_not_just_two(self) -> None:
        clearance_case = a_case()
        clearance_case.attach_document("COMMERCIAL_INVOICE", uuid4())
        clearance_case.attach_document("COMMERCIAL_INVOICE", uuid4())

        for document in list(clearance_case.documents):
            event = clearance_case.verify_document(document.id, "INSP-1")

        assert event is None
        assert clearance_case.status is AssessmentStatus.DOCUMENT_VERIFICATION

    def test_announces_completion_only_once(self) -> None:
        clearance_case = a_case_with_both_documents()
        for document in list(clearance_case.documents):
            clearance_case.verify_document(document.id, "INSP-1")

        extra = clearance_case.attach_document("BILL_OF_LADING", uuid4())
        event = clearance_case.verify_document(extra.id, "INSP-1")

        assert event is None
        assert clearance_case.status is AssessmentStatus.RISK_ASSESSMENT

    def test_reports_a_document_the_case_does_not_hold(self) -> None:
        with pytest.raises(DocumentNotFoundError):
            a_case_with_both_documents().verify_document(uuid4(), "INSP-1")

    def test_refuses_a_second_sign_off(self) -> None:
        clearance_case = a_case_with_both_documents()
        document = clearance_case.documents[0]
        clearance_case.verify_document(document.id, "INSP-1")

        with pytest.raises(DocumentAlreadyVerifiedError):
            clearance_case.verify_document(document.id, "INSP-2")

        assert document.verified_by_inspector_id == "INSP-1"

    @pytest.mark.parametrize("inspector_id", ["", "   ", None, 7, "x" * 129])
    def test_requires_an_identified_inspector(self, inspector_id: object) -> None:
        clearance_case = a_case_with_both_documents()
        document = clearance_case.documents[0]

        with pytest.raises(InvalidInspectorError):
            clearance_case.verify_document(document.id, inspector_id)  # type: ignore[arg-type]

        assert document.is_verified is False

    @pytest.mark.parametrize(
        "status", [AssessmentStatus.RELEASED, AssessmentStatus.REJECTED]
    )
    def test_refuses_to_clear_on_a_decided_case(self, status: AssessmentStatus) -> None:
        clearance_case = a_case_with_both_documents()
        document = clearance_case.documents[0]
        clearance_case.status = status

        with pytest.raises(DocumentNotVerifiableError):
            clearance_case.verify_document(document.id, "INSP-1")

        assert document.is_verified is False

    def test_knows_when_its_paperwork_is_complete(self) -> None:
        clearance_case = a_case_with_both_documents()

        assert not clearance_case.has_complete_paperwork()

        for document in list(clearance_case.documents):
            clearance_case.verify_document(document.id, "INSP-1")

        assert clearance_case.has_complete_paperwork()
