"""Application composition root.

Wires the modular monolith together: settings, imperative ORM mappings, global
RFC 9457 error handling and the HTTP router published by each module.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from modules.customs_clearance.src.api import router as customs_clearance_router
from modules.customs_clearance.src.infrastructure.database.entities import (
    start_mappers as start_customs_clearance_mappers,
)
from modules.files.src.api import router as files_router
from modules.files.src.infrastructure.database.entities import (
    start_mappers as start_files_mappers,
)
from modules.shared.config import get_settings
from modules.shared.database import dispose_engine
from modules.shared.http.exceptions import register_exception_handlers
from modules.shared.message_bus import start_message_bus_mappers
from modules.shipment.src.api import router as shipment_router
from modules.shipment.src.infrastructure.database.entities import (
    start_mappers as start_shipment_mappers,
)
from modules.shipment.src.infrastructure.message_bus import (
    register_shipment_message_destinations,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start imperative mappings on boot and release resources on shutdown."""
    start_shipment_mappers()
    start_customs_clearance_mappers()
    start_files_mappers()
    start_message_bus_mappers()
    register_shipment_message_destinations()
    logger.info("Imperative ORM mappings configured")
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="International Freight & Customs Clearance service.",
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    register_exception_handlers(app)

    app.include_router(shipment_router)
    app.include_router(customs_clearance_router)
    app.include_router(files_router)

    @app.get("/health", tags=["Operations"], summary="Liveness probe")
    async def health() -> dict[str, str]:
        """Report that the process is up."""
        return {"status": "ok", "environment": settings.app_env}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    _settings = get_settings()
    uvicorn.run(
        "main:app",
        host=_settings.app_host,
        port=_settings.app_port,
        reload=not _settings.is_production,
        log_level=_settings.app_log_level,
    )
