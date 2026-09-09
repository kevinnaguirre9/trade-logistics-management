"""HTTP composition root of the Files module.

Every vertical slice under ``features/`` exposes its own ``APIRouter`` and gets
mounted here, so the module publishes a single router to the application.
"""

from fastapi import APIRouter

from modules.files.src.features.upload_file import upload_file_controller

router = APIRouter(tags=["Files"])

router.include_router(upload_file_controller.router)
