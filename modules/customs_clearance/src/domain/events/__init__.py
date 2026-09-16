"""Domain and integration events raised by the Customs Clearance aggregates."""

from modules.customs_clearance.src.domain.events.document_verification_completed import (  # noqa: E501
    DocumentVerificationCompleted,
)

__all__ = ["DocumentVerificationCompleted"]
