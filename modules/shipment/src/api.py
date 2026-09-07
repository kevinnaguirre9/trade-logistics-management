"""HTTP composition root of the Shipment module.

Every vertical slice under ``features/`` exposes its own ``APIRouter`` and gets
mounted here, so the module publishes a single router to the application.
"""

from fastapi import APIRouter

from modules.shipment.src.features.create_draft_shipment import (
    router as create_draft_shipment_router,
)

router = APIRouter(tags=["Shipment"])

router.include_router(create_draft_shipment_router)
