"""The storage port: what the Files module needs from any storage class.

This is the abstraction the module exists for. Local volumes, GCS and S3
buckets and SFTP servers differ in every detail except the four operations
below, so the domain depends on these and the infrastructure layer resolves
them against whatever disk the caller named.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StoredObject:
    """What a backend can tell us about the bytes it just wrote."""

    size_bytes: int
    checksum: str


class FileStorage(ABC):
    """Reads and writes objects on the disks this deployment configures."""

    @property
    @abstractmethod
    def disks(self) -> tuple[str, ...]:
        """Return the names of every configured disk."""

    def supports(self, disk: str) -> bool:
        """Return ``True`` when this deployment has that disk configured."""
        return disk in self.disks

    @abstractmethod
    async def put(
        self,
        disk: str,
        key: str,
        chunks: AsyncIterator[bytes],
    ) -> StoredObject:
        """Write a stream of bytes to ``key`` on ``disk``.

        Implementations consume the stream once, and answer with the size and
        digest of what was actually written, so the caller records facts about
        the stored object rather than claims made by the client.
        """

    @abstractmethod
    async def exists(self, disk: str, key: str) -> bool:
        """Return ``True`` when something is already stored at that key."""

    @abstractmethod
    async def delete(self, disk: str, key: str) -> None:
        """Remove the object, if it is there. Deleting nothing is not an error."""
