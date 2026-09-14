"""Kinds of legal document a clearance case accepts."""

from enum import StrEnum


class DocumentType(StrEnum):
    """The paperwork customs requires before it can assess a shipment.

    Both are needed before a case can move on to risk assessment, which is why
    the set is closed: an unrecognized type would silently never satisfy that
    rule.
    """

    COMMERCIAL_INVOICE = "COMMERCIAL_INVOICE"
    BILL_OF_LADING = "BILL_OF_LADING"
