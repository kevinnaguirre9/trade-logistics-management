"""Table definitions and imperative mappings of the Files module.

Tables are declared against the shared metadata using the ``files`` schema, and
the domain objects are attached to them with
``mapper_registry.map_imperatively(...)`` inside :func:`start_mappers`.
"""

from sqlalchemy.orm import composite, relationship

from modules.files.src.domain.entities import FileReference
from modules.files.src.domain.stored_file import StoredFile
from modules.files.src.domain.value_objects import FileId, StorageLocation
from modules.files.src.infrastructure.database.entities.file_table import (
    file_references_owner_index,
    file_references_table,
    files_table,
)
from modules.shared.database import mapper_registry

_mappers_started = False


def start_mappers() -> None:
    """Attach the Files domain objects to their tables (idempotent).

    Called once by the application composition root at start-up.

    ``references`` is a real collection of the aggregate: it cascades with its
    root and is loaded eagerly, because a lazy load under asyncio would raise
    the moment a caller touched it outside the awaited query.
    """
    global _mappers_started
    if _mappers_started:
        return

    columns = files_table.c

    mapper_registry.map_imperatively(
        FileReference,
        file_references_table,
        properties={"id": file_references_table.c.id},
        exclude_properties=["created_at"],
    )

    mapper_registry.map_imperatively(
        StoredFile,
        files_table,
        properties={
            "_id": columns.id,
            "id": composite(FileId, columns.id),
            # The object key is one value object over the two columns the
            # caller supplied it in.
            "_path": columns.path,
            "_name": columns.name,
            "location": composite(StorageLocation, columns.path, columns.name),
            "references": relationship(
                FileReference,
                cascade="all, delete-orphan",
                lazy="selectin",
                passive_deletes=True,
            ),
        },
        exclude_properties=["created_at", "updated_at"],
    )

    _mappers_started = True


__all__ = [
    "file_references_owner_index",
    "file_references_table",
    "files_table",
    "start_mappers",
]
