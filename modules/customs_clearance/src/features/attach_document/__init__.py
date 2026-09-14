"""Vertical slice: attach legal document reference.

Re-exported here so callers outside the slice (the module router, the tests)
depend on the slice, not on its internal file layout.
"""

from modules.customs_clearance.src.features.attach_document.attach_document_command import (  # noqa: E501
    AttachDocumentCommand,
)
from modules.customs_clearance.src.features.attach_document.attach_document_controller import (  # noqa: E501
    AttachDocumentResponse,
    DocumentView,
    get_attach_document_handler,
    router,
)
from modules.customs_clearance.src.features.attach_document.attach_document_handler import (  # noqa: E501
    AttachDocumentHandler,
)

__all__ = [
    "AttachDocumentCommand",
    "AttachDocumentHandler",
    "AttachDocumentResponse",
    "DocumentView",
    "get_attach_document_handler",
    "router",
]
