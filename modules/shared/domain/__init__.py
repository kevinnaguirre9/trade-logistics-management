"""Building blocks shared by the modules' domain layers."""

from modules.shared.domain.errors import (
    ApplicationError,
    ConflictError,
    EntityNotFoundError,
    ForbiddenError,
    InvalidStateTransitionError,
    InvariantViolationError,
    UnauthorizedError,
)

__all__ = [
    "ApplicationError",
    "ConflictError",
    "EntityNotFoundError",
    "ForbiddenError",
    "InvalidStateTransitionError",
    "InvariantViolationError",
    "UnauthorizedError",
]
