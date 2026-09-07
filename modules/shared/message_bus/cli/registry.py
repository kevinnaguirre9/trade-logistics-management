"""What the CLI needs to know about a module to run a worker for it."""

from dataclasses import dataclass, field

from modules.shared.message_bus.errors import UnknownModuleError
from modules.shared.message_bus.handlers.message_handler import MessageHandlerRegistry


@dataclass(frozen=True, slots=True)
class ModuleBinding:
    """Binds a module name to its schema and its message handlers.

    The bindings are assembled in the worker composition root, never here: the
    shared kernel must not import a business module.
    """

    name: str
    schema: str
    handlers: MessageHandlerRegistry = field(default_factory=MessageHandlerRegistry)


class ModuleRegistry:
    """The modules a worker process can be pointed at with ``--module``."""

    def __init__(self, *bindings: ModuleBinding) -> None:
        self._bindings = {binding.name: binding for binding in bindings}

    def get(self, name: str) -> ModuleBinding:
        """Return the binding for a module name, or raise."""
        try:
            return self._bindings[name]
        except KeyError:
            available = ", ".join(self.names()) or "none"
            raise UnknownModuleError(
                f"Unknown module '{name}'. Available modules: {available}."
            ) from None

    def names(self) -> tuple[str, ...]:
        """Return every module name the worker knows."""
        return tuple(sorted(self._bindings))
