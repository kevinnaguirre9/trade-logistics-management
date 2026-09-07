"""Domain exceptions of the Customs Clearance module.

They subclass the shared, framework-agnostic hierarchy in
``modules.shared.domain.errors`` so the transport layers can translate them
into RFC 9457 Problem Details without extra mapping code.
"""

from modules.customs_clearance.src.domain.exceptions.clearance_exceptions import (
    ClearanceCaseNotFoundError,
    CurrencyMismatchError,
    InvalidCaseIdError,
    InvalidMoneyError,
    InvalidShipmentReferenceError,
)

__all__ = [
    "ClearanceCaseNotFoundError",
    "CurrencyMismatchError",
    "InvalidCaseIdError",
    "InvalidMoneyError",
    "InvalidShipmentReferenceError",
]
