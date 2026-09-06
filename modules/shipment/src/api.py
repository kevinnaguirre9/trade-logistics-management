"""HTTP composition root of the Shipment module.

Every vertical slice under ``features/`` exposes its own ``APIRouter`` and gets
mounted here, so the module publishes a single router to the application.
"""

from fastapi import APIRouter

router = APIRouter(tags=["Shipment"])

# Feature routers are included as slices are implemented, e.g.:
# from modules.shipment.src.features.create_draft_shipment import (
#     create_draft_shipment_controller,
# )
# router.include_router(create_draft_shipment_controller.router)
