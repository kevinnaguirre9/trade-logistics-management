"""Storage adapters of the Files module."""

from modules.files.src.infrastructure.storage.disks import (
    AWS_DISK,
    GCP_DISK,
    LOCAL_DISK,
    SFTP_DISK,
    DiskConfig,
    build_disk_registry,
)
from modules.files.src.infrastructure.storage.fsspec_file_storage import (
    FsspecFileStorage,
)

__all__ = [
    "AWS_DISK",
    "GCP_DISK",
    "LOCAL_DISK",
    "SFTP_DISK",
    "DiskConfig",
    "FsspecFileStorage",
    "build_disk_registry",
]
