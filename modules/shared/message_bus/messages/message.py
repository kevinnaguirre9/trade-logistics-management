"""Integration messages: the plain Python classes that cross the broker."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from typing import Any, ClassVar, Self


# No ``slots=True`` here: it makes dataclass rebuild the class, which leaves
# the ``__class__`` cell of ``__init_subclass__`` pointing at the original and
# breaks the zero-argument ``super()`` call below. Subclasses may still use it.
@dataclass(frozen=True)
class IntegrationMessage:
    """Base class for the events and commands published to RabbitMQ.

    Subclasses are frozen dataclasses with no framework dependency, so a module
    can declare its contract without importing SQLAlchemy, aio-pika or Pydantic.

    ``message_type`` travels in the AMQP ``type`` property and is what the
    consumer matches handlers on. It defaults to the class name, so the name
    has to read as domain behaviour (``ShipmentManifestFinalized``), never as a
    CRUD operation.
    """

    message_type: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Default ``message_type`` to the subclass name."""
        super().__init_subclass__(**kwargs)
        if not cls.__dict__.get("message_type"):
            cls.message_type = cls.__name__

    def to_body(self) -> dict[str, Any]:
        """Return the JSON-serializable body carried by the message."""
        return asdict(self)

    @classmethod
    def from_body(cls, body: Mapping[str, Any]) -> Self:
        """Rebuild the message from a decoded body, ignoring unknown keys.

        Unknown keys are dropped on purpose: a publisher that adds a field must
        not break consumers that were written against the previous contract.
        """
        known = {field.name for field in fields(cls)}
        return cls(**{key: value for key, value in body.items() if key in known})
