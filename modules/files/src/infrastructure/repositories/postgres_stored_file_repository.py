"""PostgreSQL implementation of :class:`StoredFileRepository`."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from modules.files.src.domain.entities import FileReference
from modules.files.src.domain.exceptions import FileAlreadyStoredError
from modules.files.src.domain.repositories import StoredFileRepository
from modules.files.src.domain.stored_file import StoredFile
from modules.files.src.domain.value_objects import FileId

#: The constraint that guards one object key per disk.
LOCATION_CONSTRAINT = "uq_files_disk_path_name"


class PostgresStoredFileRepository(StoredFileRepository):
    """Stores whole aggregates in ``files.files`` and ``files.file_references``.

    The session (and therefore the transaction) is owned by the caller, so the
    repository only flushes: committing is the job of the request scope.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def persist(self, stored_file: StoredFile) -> None:
        """Insert the aggregate, or flush the changes of a tracked one.

        The unique constraint on the location is the authority on collisions,
        not the ``exists()`` check that precedes the write: two uploads can
        both find the key free and race to take it. Losing that race is the
        same conflict the caller was already told about, so it is reported the
        same way rather than as an unexpected failure.
        """
        self._session.add(stored_file)
        try:
            await self._session.flush()
        except IntegrityError as error:
            if LOCATION_CONSTRAINT not in str(error.orig or error):
                raise
            raise FileAlreadyStoredError(
                f"'{stored_file.key}' already exists on disk '{stored_file.disk}'."
            ) from error

    async def find_by_id(self, file_id: FileId) -> StoredFile | None:
        """Return the aggregate with the given identity, or ``None``."""
        statement = select(StoredFile).where(StoredFile.id == file_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def find_by_reference(
        self,
        context: str,
        entity_type: str,
        entity_id: str | None = None,
    ) -> list[StoredFile]:
        """Return every file referencing that thing in another context."""
        conditions = [
            FileReference.context == context,
            FileReference.entity_type == entity_type,
        ]
        if entity_id is not None:
            conditions.append(FileReference.entity_id == entity_id)

        statement = (
            select(StoredFile)
            .join(StoredFile.references)
            .where(*conditions)
            .order_by(FileReference.id)
        )
        result = await self._session.execute(statement)
        return list(result.unique().scalars().all())
