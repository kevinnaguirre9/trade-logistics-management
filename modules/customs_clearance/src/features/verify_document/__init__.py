"""Vertical slice: verify document.

Re-exported here so callers outside the slice (the module router, the tests)
depend on the slice, not on its internal file layout.
"""

from modules.customs_clearance.src.features.verify_document.verify_document_command import (  # noqa: E501
    VerifyDocumentCommand,
)
from modules.customs_clearance.src.features.verify_document.verify_document_controller import (  # noqa: E501
    VerifiedDocumentView,
    VerifyDocumentResponse,
    get_verify_document_handler,
    router,
)
from modules.customs_clearance.src.features.verify_document.verify_document_handler import (  # noqa: E501
    VerifyDocumentHandler,
)

__all__ = [
    "VerifiedDocumentView",
    "VerifyDocumentCommand",
    "VerifyDocumentHandler",
    "VerifyDocumentResponse",
    "get_verify_document_handler",
    "router",
]
