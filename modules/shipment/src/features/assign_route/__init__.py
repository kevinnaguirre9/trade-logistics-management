"""Vertical slice: assign complex route (controller + command + handler).

Re-exported here so callers outside the slice (the module router, the tests)
depend on the slice, not on its internal file layout.
"""

from modules.shipment.src.features.assign_route.assign_route_command import (
    AssignRouteCommand,
)
from modules.shipment.src.features.assign_route.assign_route_controller import (
    AssignRouteResponse,
    RouteView,
    get_assign_route_handler,
    router,
)
from modules.shipment.src.features.assign_route.assign_route_handler import (
    AssignRouteHandler,
)

__all__ = [
    "AssignRouteCommand",
    "AssignRouteHandler",
    "AssignRouteResponse",
    "RouteView",
    "get_assign_route_handler",
    "router",
]
