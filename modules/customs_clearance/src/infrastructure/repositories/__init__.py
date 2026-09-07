"""PostgreSQL repository implementations of the Customs Clearance module."""

from modules.customs_clearance.src.infrastructure.repositories.postgres_clearance_case_repository import (  # noqa: E501
    PostgresClearanceCaseRepository,
)

__all__ = ["PostgresClearanceCaseRepository"]
