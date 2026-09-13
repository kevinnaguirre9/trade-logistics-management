"""The one storage adapter: fsspec, driving every configured disk.

fsspec presents local volumes, GCS and S3 buckets and SFTP servers through a
single filesystem interface, so this class is the whole infrastructure side of
:class:`~modules.files.src.domain.services.FileStorage`. Adding a storage
class is a :class:`~modules.files.src.infrastructure.storage.disks.DiskConfig`
entry and a driver in the image, not another adapter.

Those drivers are synchronous, so every call that touches a backend is handed
to a worker thread: the event loop keeps serving requests while an upload is in
flight.
"""

import hashlib
import logging
import shutil
import tempfile
from collections.abc import AsyncIterator, Mapping
from typing import IO, Any

import fsspec
from anyio import to_thread

from modules.files.src.domain.exceptions import (
    FileTooLargeError,
    StorageBackendUnavailableError,
    UnknownStorageDiskError,
)
from modules.files.src.domain.services import FileStorage, StoredObject
from modules.files.src.infrastructure.storage.disks import DiskConfig

logger = logging.getLogger(__name__)

#: Uploads stay in memory up to this size and spill to a temporary file after
#: it, so a large upload never has to fit in RAM.
SPOOL_THRESHOLD_BYTES = 1024 * 1024

#: Digest recorded for every stored object.
CHECKSUM_ALGORITHM = "sha256"


class FsspecFileStorage(FileStorage):
    """Reads and writes objects on any disk fsspec has a driver for."""

    def __init__(
        self,
        disks: Mapping[str, DiskConfig],
        max_upload_bytes: int,
    ) -> None:
        self._disks = dict(disks)
        self._max_upload_bytes = max_upload_bytes

    @property
    def disks(self) -> tuple[str, ...]:
        """Return the names of every configured disk."""
        return tuple(self._disks)

    async def put(
        self,
        disk: str,
        key: str,
        chunks: AsyncIterator[bytes],
    ) -> StoredObject:
        """Spool the stream, measure it, then write it to the disk."""
        config = self._config(disk)

        digest = hashlib.new(CHECKSUM_ALGORITHM)
        size = 0

        with tempfile.SpooledTemporaryFile(max_size=SPOOL_THRESHOLD_BYTES) as spool:
            async for chunk in chunks:
                size += len(chunk)
                if size > self._max_upload_bytes:
                    raise FileTooLargeError(
                        f"The upload exceeds the maximum of "
                        f"{self._max_upload_bytes} bytes."
                    )
                digest.update(chunk)
                spool.write(chunk)

            spool.seek(0)
            await to_thread.run_sync(self._write, config, key, spool)

        logger.info("Stored %s bytes at %s on disk '%s'.", size, key, config.name)
        return StoredObject(
            size_bytes=size,
            checksum=f"{CHECKSUM_ALGORITHM}:{digest.hexdigest()}",
        )

    async def exists(self, disk: str, key: str) -> bool:
        """Return ``True`` when something is already stored at that key."""
        config = self._config(disk)
        return await to_thread.run_sync(self._exists, config, key)

    async def delete(self, disk: str, key: str) -> None:
        """Remove the object, if it is there."""
        config = self._config(disk)
        await to_thread.run_sync(self._delete, config, key)

    # -- blocking half, always called in a worker thread ---------------------

    def _write(self, config: DiskConfig, key: str, source: IO[bytes]) -> None:
        """Copy the spooled bytes onto the disk."""
        filesystem = self._filesystem(config)
        target = self._absolute(config, key)

        parent, separator, _ = target.rpartition("/")
        try:
            if separator:
                filesystem.makedirs(parent, exist_ok=True)
            with filesystem.open(target, "wb") as destination:
                shutil.copyfileobj(source, destination)
        except OSError as error:
            raise StorageBackendUnavailableError(
                f"Disk '{config.name}' refused the write: {error}"
            ) from error

    def _exists(self, config: DiskConfig, key: str) -> bool:
        """Return whether the key is taken on that disk."""
        filesystem = self._filesystem(config)
        try:
            return bool(filesystem.exists(self._absolute(config, key)))
        except OSError as error:
            raise StorageBackendUnavailableError(
                f"Disk '{config.name}' could not be read: {error}"
            ) from error

    def _delete(self, config: DiskConfig, key: str) -> None:
        """Remove the key from that disk, tolerating an absent object."""
        filesystem = self._filesystem(config)
        target = self._absolute(config, key)
        try:
            if filesystem.exists(target):
                filesystem.rm(target)
        except OSError as error:
            raise StorageBackendUnavailableError(
                f"Disk '{config.name}' refused the delete: {error}"
            ) from error

    # -- helpers -------------------------------------------------------------

    def _config(self, disk: str) -> DiskConfig:
        """Return the configuration of a disk, or say why it is unusable."""
        config = self._disks.get(disk)
        if config is None:
            raise UnknownStorageDiskError(
                f"'{disk}' is not a configured disk.",
                extensions={"configured_disks": list(self._disks)},
            )
        return config

    def _filesystem(self, config: DiskConfig) -> Any:
        """Return the fsspec filesystem of a disk.

        fsspec caches instances per protocol and options, so this is cheap to
        call per operation and stays correct when settings differ per disk.
        """
        try:
            return fsspec.filesystem(config.protocol, **config.options)
        except ImportError as error:
            extra = f' Install it with pip install ".[{config.extra}]".'
            raise StorageBackendUnavailableError(
                f"Disk '{config.name}' needs the '{config.protocol}' driver, "
                f"which is not installed in this image."
                f"{extra if config.extra else ''}"
            ) from error
        except ValueError as error:
            raise StorageBackendUnavailableError(
                f"Disk '{config.name}' is misconfigured: {error}"
            ) from error

    @staticmethod
    def _absolute(config: DiskConfig, key: str) -> str:
        """Return the backend path of a key, under the root of its disk."""
        root = config.root.rstrip("/")
        return f"{root}/{key}" if root else key
