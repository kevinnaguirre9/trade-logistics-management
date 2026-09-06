"""RFC 9457 (Problem Details for HTTP APIs) representation."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

PROBLEM_CONTENT_TYPE = "application/problem+json"

#: Base URI used to build the ``type`` member of a problem document.
PROBLEM_TYPE_BASE_URI = "https://trade-logistics.local/problems"


class ProblemDetails(BaseModel):
    """A problem document as defined by RFC 9457.

    Extension members (for example ``errors`` for validation failures) are
    allowed and serialized alongside the standard members.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    type: str = Field(
        default="about:blank",
        description="URI reference identifying the problem type.",
    )
    title: str = Field(description="Short, human-readable summary.")
    status: int = Field(description="HTTP status code generated for this occurrence.")
    detail: str | None = Field(
        default=None,
        description="Human-readable explanation specific to this occurrence.",
    )
    instance: str | None = Field(
        default=None,
        description="URI reference identifying this specific occurrence.",
    )


def build_problem_type_uri(error_type: str) -> str:
    """Return the canonical ``type`` URI for an error slug."""
    return f"{PROBLEM_TYPE_BASE_URI}/{error_type}"


def build_problem_details(
    *,
    status: int,
    title: str,
    detail: str | None = None,
    error_type: str | None = None,
    instance: str | None = None,
    extensions: dict[str, Any] | None = None,
) -> ProblemDetails:
    """Assemble a :class:`ProblemDetails` document."""
    return ProblemDetails(
        type=build_problem_type_uri(error_type) if error_type else "about:blank",
        title=title,
        status=status,
        detail=detail,
        instance=instance,
        **(extensions or {}),
    )
