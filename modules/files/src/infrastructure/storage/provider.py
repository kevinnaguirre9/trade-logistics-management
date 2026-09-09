"""Process-wide storage adapter, built once from the environment."""

from functools import lru_cache

from modules.files.src.domain.services import FileStorage
from modules.files.src.infrastructure.storage.disks import build_disk_registry
from modules.files.src.infrastructure.storage.fsspec_file_storage import (
    FsspecFileStorage,
)
from modules.shared.config import get_settings


@lru_cache
def get_file_storage() -> FileStorage:
    """Return the storage adapter with every configured disk mounted."""
    settings = get_settings()
    return FsspecFileStorage(
        disks=build_disk_registry(settings),
        max_upload_bytes=settings.files_max_upload_bytes,
    )
