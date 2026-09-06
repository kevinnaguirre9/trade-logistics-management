"""HTTP error translation (RFC 9457 Problem Details)."""

from modules.shared.http.exceptions.handlers import register_exception_handlers
from modules.shared.http.exceptions.problem_details import (
    PROBLEM_CONTENT_TYPE,
    ProblemDetails,
    build_problem_details,
)

__all__ = [
    "PROBLEM_CONTENT_TYPE",
    "ProblemDetails",
    "build_problem_details",
    "register_exception_handlers",
]
