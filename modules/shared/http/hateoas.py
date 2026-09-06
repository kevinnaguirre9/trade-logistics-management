"""Minimal hypermedia helpers for task-based endpoints.

Command endpoints answer with the affected resource identifier plus the set of
next allowed tasks, so clients discover the workflow instead of hard-coding it.
"""

from pydantic import BaseModel, Field


class Link(BaseModel):
    """A single hypermedia control."""

    rel: str = Field(description="Relation name, e.g. 'assign-route'.")
    href: str = Field(description="Target URI of the linked task.")
    method: str = Field(default="GET", description="HTTP method to invoke.")


class HypermediaResponse(BaseModel):
    """Base response DTO carrying hypermedia controls."""

    links: list[Link] = Field(default_factory=list, alias="_links")

    model_config = {"populate_by_name": True}
