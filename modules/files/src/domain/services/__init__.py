"""Domain service ports of the Files module."""

from modules.files.src.domain.services.file_storage import (
    FileStorage,
    StoredObject,
)

__all__ = ["FileStorage", "StoredObject"]
