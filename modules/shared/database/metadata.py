"""Shared SQLAlchemy metadata and imperative-mapping registry.

Every module declares its own ``Table`` objects (in
``<module>/src/infrastructure/database/entities``) against this single
``MetaData`` instance, using its own PostgreSQL schema. Sharing the metadata
keeps Alembic autogeneration aware of the whole database while the schemas keep
the modules physically isolated.

Domain objects stay free of ORM decorators: they are attached to the tables
through :data:`mapper_registry` (imperative / classical mapping).
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import registry

# Deterministic constraint names keep Alembic migrations stable and reversible.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)

mapper_registry = registry(metadata=metadata)
