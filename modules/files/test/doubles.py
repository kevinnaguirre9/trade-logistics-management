"""Test doubles shared by the Files test suite."""

import hashlib
from collections.abc import AsyncIterator

from modules.files.src.domain.exceptions import (
    FileAlreadyStoredError,
    FileTooLargeError,
)
from modules.files.src.domain.repositories import StoredFileRepository
from modules.files.src.domain.services import FileStorage, StoredObject
from modules.files.src.domain.stored_file import StoredFile
from modules.files.src.domain.value_objects import FileId


class InMemoryFileStorage(FileStorage):
    """A storage backend that keeps its objects in a dictionary.

    Behaves like the real adapter where it matters: it consumes the stream
    once, measures and digests what it actually received, and enforces the
    upload ceiling while reading.
    """

    def __init__(
        self,
        *disks: str,
        max_upload_bytes: int = 1024 * 1024,
    ) -> None:
        self._disks = disks or ("local",)
        self._max_upload_bytes = max_upload_bytes
        self.objects: dict[tuple[str, str], bytes] = {}

    @property
    def disks(self) -> tuple[str, ...]:
        return self._disks

    async def put(
        self,
        disk: str,
        key: str,
        chunks: AsyncIterator[bytes],
    ) -> StoredObject:
        payload = bytearray()
        async for chunk in chunks:
            payload.extend(chunk)
            if len(payload) > self._max_upload_bytes:
                raise FileTooLargeError(
                    f"The upload exceeds the maximum of {self._max_upload_bytes} bytes."
                )

        self.objects[(disk, key)] = bytes(payload)
        return StoredObject(
            size_bytes=len(payload),
            checksum=f"sha256:{hashlib.sha256(payload).hexdigest()}",
        )

    async def exists(self, disk: str, key: str) -> bool:
        return (disk, key) in self.objects

    async def delete(self, disk: str, key: str) -> None:
        self.objects.pop((disk, key), None)


class InMemoryStoredFileRepository(StoredFileRepository):
    """Test double keeping the aggregates in a list."""

    def __init__(self, *files: StoredFile) -> None:
        self.persisted: list[StoredFile] = list(files)

    async def persist(self, stored_file: StoredFile) -> None:
        if stored_file not in self.persisted:
            self.persisted.append(stored_file)

    async def find_by_id(self, file_id: FileId) -> StoredFile | None:
        return next(
            (item for item in self.persisted if item.id == file_id),
            None,
        )

    async def find_by_reference(
        self,
        context: str,
        entity_type: str,
        entity_id: str | None = None,
    ) -> list[StoredFile]:
        return [
            item
            for item in self.persisted
            if item.is_referenced_by(context, entity_type, entity_id)
        ]


class UnwritableStoredFileRepository(InMemoryStoredFileRepository):
    """A repository whose insert always fails, to exercise compensation."""

    async def persist(self, stored_file: StoredFile) -> None:
        raise RuntimeError("the insert failed")


class ContendedStoredFileRepository(InMemoryStoredFileRepository):
    """A repository that lost the race for the location, as PostgreSQL sees it."""

    async def persist(self, stored_file: StoredFile) -> None:
        raise FileAlreadyStoredError(
            f"'{stored_file.key}' already exists on disk '{stored_file.disk}'."
        )
