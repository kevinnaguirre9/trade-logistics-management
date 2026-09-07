"""Unit tests for the Customs Clearance domain model."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from modules.customs_clearance.src.domain.clearance_case import ClearanceCase
from modules.customs_clearance.src.domain.enums import AssessmentStatus
from modules.customs_clearance.src.domain.exceptions import (
    CurrencyMismatchError,
    InvalidCaseIdError,
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
