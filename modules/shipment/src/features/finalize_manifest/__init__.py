"""Vertical slice: finalize cargo manifest (controller + command + handler).

Re-exported here so callers outside the slice (the module router, the tests)
depend on the slice, not on its internal file layout.
"""

from modules.shipment.src.features.finalize_manifest.finalize_manifest_command import (
    FinalizeManifestCommand,
)
from modules.shipment.src.features.finalize_manifest.finalize_manifest_controller import (  # noqa: E501
    FinalizeManifestResponse,
    ManifestView,
    get_finalize_manifest_handler,
    router,
)
from modules.shipment.src.features.finalize_manifest.finalize_manifest_handler import (
    FinalizeManifestHandler,
)

__all__ = [
    "FinalizeManifestCommand",
    "FinalizeManifestHandler",
    "FinalizeManifestResponse",
    "ManifestView",
    "get_finalize_manifest_handler",
    "router",
]
