"""Command handler of the *upload file* slice."""

import logging
from collections.abc import AsyncIterator

from modules.files.src.domain.entities import FileReference
from modules.files.src.domain.exceptions import (
    FileAlreadyStoredError,
    UnknownStorageDiskError,
)
from modules.files.src.domain.repositories import StoredFileRepository
from modules.files.src.domain.services import FileStorage
from modules.files.src.domain.stored_file import StoredFile
from modules.files.src.domain.value_objects import FileId, StorageLocation
from modules.files.src.features.upload_file.upload_file_command import (
    UploadFileCommand,
)

logger = logging.getLogger(__name__)


class UploadFileHandler:
    """Writes the bytes to a disk, then records what was written.

    The two halves cannot share a transaction: one is a storage backend and the
    other is PostgreSQL. The order is deliberate - bytes first, row second - so
    a failure never leaves a file uuid pointing at nothing. The opposite
    failure, a row that never commits, leaves an unreferenced object on the
    disk; the handler removes it when the insert fails, and a later commit
    failure is left for a sweeper rather than pretended away.
    """

    def __init__(self, files: StoredFileRepository, storage: FileStorage) -> None:
        self._files = files
        self._storage = storage

    async def handle(
        self,
        command: UploadFileCommand,
        chunks: AsyncIterator[bytes],
    ) -> StoredFile:
        """Store the upload and register it against its owning aggregates."""
        if not self._storage.supports(command.disk):
            raise UnknownStorageDiskError(
                f"'{command.disk}' is not a configured disk.",
                extensions={"configured_disks": list(self._storage.disks)},
            )

        location = StorageLocation(path=command.path, name=command.name)

        if await self._storage.exists(command.disk, location.key):
            raise FileAlreadyStoredError(
                f"'{location.key}' already exists on disk '{command.disk}'."
            )

        written = await self._storage.put(command.disk, location.key, chunks)

        stored_file = StoredFile.register(
            file_id=FileId.generate(),
            disk=command.disk,
            location=location,
            size_bytes=written.size_bytes,
            content_type=command.content_type,
            checksum=written.checksum,
            metadata=command.metadata,
            references=[
                FileReference.declare(
                    entity_type=reference.entity_type,
                    entity_id=reference.entity_id,
                    context=reference.context,
                    entity_uuid=reference.uuid,
                )
                for reference in command.references
            ],
        )

        try:
            await self._files.persist(stored_file)
        except FileAlreadyStoredError:
            # Lost a race for the key: the object there belongs to whoever won,
            # so it must be left alone. Ours is gone already - both writes used
            # the same key - which is the cost of letting the winner keep it.
            raise
        except Exception:
            # The bytes are on the disk and nothing will ever point at them, so
            # take them back out before reporting the failure.
            logger.exception(
                "Could not record %s on disk '%s'; removing the stored object.",
                location.key,
                command.disk,
            )
            await self._storage.delete(command.disk, location.key)
            raise

        return stored_file
