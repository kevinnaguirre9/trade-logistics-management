"""PostgreSQL repository implementations of the Files module."""

from modules.files.src.infrastructure.repositories.postgres_stored_file_repository import (  # noqa: E501
    PostgresStoredFileRepository,
)

__all__ = ["PostgresStoredFileRepository"]
