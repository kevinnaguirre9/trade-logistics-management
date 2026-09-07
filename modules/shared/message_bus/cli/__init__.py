"""The worker CLI: ``dispatch-messages`` and ``handle-messages``."""

from modules.shared.message_bus.cli.app import build_cli
from modules.shared.message_bus.cli.registry import ModuleBinding, ModuleRegistry

__all__ = [
    "ModuleBinding",
    "ModuleRegistry",
    "build_cli",
]
