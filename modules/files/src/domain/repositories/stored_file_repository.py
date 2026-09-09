"""Repository interface of the StoredFile aggregate."""

from abc import ABC, abstractmethod

from modules.files.src.domain.stored_file import StoredFile
from modules.files.src.domain.value_objects import FileId


class StoredFileRepository(ABC):
    """Persists and retrieves whole :class:`StoredFile` aggregates."""

    @abstractmethod
    async def persist(self, stored_file: StoredFile) -> None:
        """Insert or update the whole aggregate, references included.

        The surrounding transaction is owned by the request scope, so
        implementations must not commit.
        """

    @abstractmethod
    async def find_by_id(self, file_id: FileId) -> StoredFile | None:
        """Return the aggregate with the given identity, or ``None``."""

    @abstractmethod
    async def find_by_reference(
        self,
        context: str,
        entity_type: str,
        entity_id: str | None = None,
    ) -> list[StoredFile]:
        """Return every file referencing that thing in another context.

        Omitting ``entity_id`` returns the files of every entity of that type,
        which is also the only way to reach references that carry no
        identifier.
        """
