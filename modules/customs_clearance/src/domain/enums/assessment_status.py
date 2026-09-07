"""Lifecycle of a customs clearance case."""

from enum import StrEnum


class AssessmentStatus(StrEnum):
    """States a clearance case moves through, in regulatory order."""

    OPENED = "Opened"
    DOCUMENT_VERIFICATION = "DocumentVerification"
    RISK_ASSESSMENT = "RiskAssessment"
    DUTY_PAYMENT_PENDING = "DutyPaymentPending"
    RELEASED = "Released"
    REJECTED = "Rejected"
