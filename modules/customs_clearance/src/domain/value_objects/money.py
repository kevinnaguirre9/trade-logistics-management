"""A monetary amount in a single currency."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from modules.customs_clearance.src.domain.exceptions import (
    CurrencyMismatchError,
    InvalidMoneyError,
)

#: Money is stored and compared to the minor unit (cents).
MINOR_UNIT = Decimal("0.01")

#: ISO 4217 alphabetic codes are exactly three letters.
CURRENCY_CODE_LENGTH = 3


@dataclass(frozen=True, slots=True)
class Money:
    """An amount of money, rounded to the minor unit of its currency.

    Invariants:

    * the amount is never negative: customs deals in duties and declared
      values, neither of which can be owed backwards;
    * the amount is rounded half-up to two decimals on construction, so two
      values that represent the same money compare equal;
    * arithmetic and comparison across currencies is refused. Converting is a
      decision with a rate and a date attached, so it belongs to an explicit
      converter, not to an operator.
    """

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        """Normalize the currency and round the amount to the minor unit."""
        currency = self._validated_currency(self.currency)
        amount = self._validated_amount(self.amount)

        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "amount", amount)

    @staticmethod
    def _validated_currency(value: object) -> str:
        """Return the normalized ISO 4217 code or raise."""
        if not isinstance(value, str):
            raise InvalidMoneyError("The currency must be a string.")

        code = value.strip().upper()
        if len(code) != CURRENCY_CODE_LENGTH or not code.isalpha():
            raise InvalidMoneyError(
                f"'{value}' is not a valid ISO 4217 currency code; expected "
                "three letters such as 'EUR'."
            )
        return code

    @staticmethod
    def _validated_amount(value: object) -> Decimal:
        """Return the amount as a non-negative, rounded ``Decimal`` or raise."""
        if isinstance(value, bool) or not isinstance(
            value, Decimal | int | float | str
        ):
            raise InvalidMoneyError("The amount must be a number.")

        try:
            # str() keeps a float from dragging its binary representation in.
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise InvalidMoneyError(f"'{value}' is not a valid amount.") from None

        if not amount.is_finite():
            raise InvalidMoneyError("The amount must be a finite number.")
        if amount < 0:
            raise InvalidMoneyError("The amount cannot be negative.")

        return amount.quantize(MINOR_UNIT, rounding=ROUND_HALF_UP)

    @classmethod
    def zero(cls, currency: str) -> "Money":
        """Return nothing owed, in the given currency."""
        return cls(amount=Decimal("0"), currency=currency)

    @staticmethod
    def from_columns(
        amount: Decimal | None,
        currency: str | None,
    ) -> "Money | None":
        """Rebuild from its columns (SQLAlchemy composite factory).

        A row where both columns are ``NULL`` means no amount has been set yet,
        so ``None`` is returned instead of an invalid value object.
        """
        if amount is None and currency is None:
            return None
        return Money(
            amount=amount,  # type: ignore[arg-type]
            currency=currency,  # type: ignore[arg-type]
        )

    def add(self, other: "Money") -> "Money":
        """Return the sum, refusing to mix currencies."""
        self._assert_same_currency(other)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def subtract(self, other: "Money") -> "Money":
        """Return the difference, refusing to mix currencies."""
        self._assert_same_currency(other)
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def covers(self, other: "Money") -> bool:
        """Return ``True`` when this amount matches or exceeds ``other``."""
        self._assert_same_currency(other)
        return self.amount >= other.amount

    def percentage(self, percent: Decimal | int | float) -> "Money":
        """Return a percentage of this amount, in the same currency."""
        return Money(
            amount=self.amount * Decimal(str(percent)) / Decimal("100"),
            currency=self.currency,
        )

    def _assert_same_currency(self, other: "Money") -> None:
        """Raise unless both amounts are in the same currency."""
        if not isinstance(other, Money):
            raise CurrencyMismatchError("Only two monetary amounts can be combined.")
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot combine {self.currency} with {other.currency} without "
                "an explicit converter."
            )

    def __composite_values__(self) -> tuple[Decimal, str]:
        """Return the column values used by the SQLAlchemy composite."""
        return (self.amount, self.currency)

    def __str__(self) -> str:
        """Return the amount as ``123.45 EUR``."""
        return f"{self.amount} {self.currency}"
