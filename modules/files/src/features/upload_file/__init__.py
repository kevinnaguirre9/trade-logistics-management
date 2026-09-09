"""Vertical slice: upload file (controller + command + handler).

Re-exported here so callers outside the slice (the module router, the tests)
depend on the slice, not on its internal file layout.
"""

from modules.files.src.features.upload_file.upload_file_command import (
    FileReferenceInput,
    UploadFileCommand,
)
from modules.files.src.features.upload_file.upload_file_controller import (
    FileReferenceView,
    UploadFileResponse,
    get_upload_file_handler,
    router,
)
from modules.files.src.features.upload_file.upload_file_handler import (
    UploadFileHandler,
)

__all__ = [
    "FileReferenceInput",
    "FileReferenceView",
    "UploadFileCommand",
    "UploadFileHandler",
    "UploadFileResponse",
    "get_upload_file_handler",
    "router",
]
