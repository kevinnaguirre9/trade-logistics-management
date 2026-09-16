"""HTTP composition root of the Customs Clearance module.

Every vertical slice under ``features/`` exposes its own ``APIRouter`` and gets
mounted here, so the module publishes a single router to the application.
"""

from fastapi import APIRouter

from modules.customs_clearance.src.features.attach_document import (
    attach_document_controller,
)
from modules.customs_clearance.src.features.verify_document import (
    verify_document_controller,
)

router = APIRouter(tags=["Customs Clearance"])

router.include_router(attach_document_controller.router)
router.include_router(verify_document_controller.router)
