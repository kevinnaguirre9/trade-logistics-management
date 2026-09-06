"""Shared persistence infrastructure: metadata, mappers and sessions."""

from modules.shared.database.metadata import (
    NAMING_CONVENTION,
    mapper_registry,
    metadata,
)
from modules.shared.database.session import (
    dispose_engine,
    get_engine,
    get_session,
    get_session_factory,
)

__all__ = [
    "NAMING_CONVENTION",
    "dispose_engine",
    "get_engine",
    "get_session",
    "get_session_factory",
    "mapper_registry",
    "metadata",
]
