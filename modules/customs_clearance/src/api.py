"""HTTP composition root of the Customs Clearance module.

Every vertical slice under ``features/`` exposes its own ``APIRouter`` and gets
mounted here, so the module publishes a single router to the application.
"""

from fastapi import APIRouter

router = APIRouter(tags=["Customs Clearance"])

# Feature routers are included as slices are implemented, e.g.:
# from modules.customs_clearance.src.features.attach_document import (
#     attach_document_controller,
# )
# router.include_router(attach_document_controller.router)
