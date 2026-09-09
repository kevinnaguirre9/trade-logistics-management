"""Value objects of the Files module (pure Python, no ORM)."""

from modules.files.src.domain.value_objects.file_id import FileId
from modules.files.src.domain.value_objects.storage_location import (
    TRAVERSAL_SEGMENTS,
    StorageLocation,
)

__all__ = ["TRAVERSAL_SEGMENTS", "FileId", "StorageLocation"]
