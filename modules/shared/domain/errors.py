"""Framework-agnostic error hierarchy shared by every module.

These classes carry no FastAPI/Starlette import on purpose: the domain and
application layers raise them, and the HTTP layer
(``modules.shared.http.exceptions``) is the only place that knows how to turn
them into an RFC 9457 Problem Details response.
"""

from typing import Any


class ApplicationError(Exception):
    """Base class for every expected, translatable failure."""

    status_code: int = 500
    title: str = "Internal Server Error"
    error_type: str = "internal-server-error"

    def __init__(
        self,
        detail: str,
        *,
        extensions: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.extensions = extensions or {}


class InvariantViolationError(ApplicationError):
    """A value object or aggregate invariant was violated."""

    status_code = 422
    title = "Invariant Violation"
    error_type = "invariant-violation"


class InvalidStateTransitionError(ApplicationError):
    """The aggregate cannot perform the operation in its current state."""

    status_code = 409
    title = "Invalid State Transition"
    error_type = "invalid-state-transition"


class EntityNotFoundError(ApplicationError):
    """The requested aggregate or entity does not exist."""

    status_code = 404
    title = "Resource Not Found"
    error_type = "resource-not-found"


class ConflictError(ApplicationError):
    """The operation conflicts with the current state of the resource."""

    status_code = 409
    title = "Conflict"
    error_type = "conflict"


class UnauthorizedError(ApplicationError):
    """The caller is not authenticated."""

    status_code = 401
    title = "Unauthorized"
    error_type = "unauthorized"


class ForbiddenError(ApplicationError):
    """The caller is authenticated but not allowed to perform the action."""

    status_code = 403
    title = "Forbidden"
    error_type = "forbidden"
