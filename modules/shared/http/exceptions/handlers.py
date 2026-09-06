"""Global exception handlers translating failures into Problem Details."""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from modules.shared.domain.errors import ApplicationError
from modules.shared.http.exceptions.problem_details import (
    PROBLEM_CONTENT_TYPE,
    ProblemDetails,
    build_problem_details,
)

logger = logging.getLogger(__name__)


def _problem_response(problem: ProblemDetails, status_code: int) -> JSONResponse:
    """Serialize a problem document with the RFC 9457 media type."""
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(exclude_none=True),
        media_type=PROBLEM_CONTENT_TYPE,
    )


async def application_error_handler(
    request: Request,
    exc: ApplicationError,
) -> JSONResponse:
    """Map an expected domain/application failure."""
    problem = build_problem_details(
        status=exc.status_code,
        title=exc.title,
        detail=exc.detail,
        error_type=exc.error_type,
        instance=str(request.url.path),
        extensions=exc.extensions,
    )
    return _problem_response(problem, exc.status_code)


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Map a request payload that failed Pydantic validation."""
    errors = [
        {
            "location": list(error.get("loc", [])),
            "message": error.get("msg", ""),
            "type": error.get("type", ""),
        }
        for error in exc.errors()
    ]
    problem = build_problem_details(
        status=HTTPStatus.UNPROCESSABLE_ENTITY,
        title="Request Validation Failed",
        detail="The request payload did not satisfy the expected contract.",
        error_type="request-validation-failed",
        instance=str(request.url.path),
        extensions={"errors": errors},
    )
    return _problem_response(problem, HTTPStatus.UNPROCESSABLE_ENTITY)


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Map framework-raised HTTP errors (404 routing, 405, ...)."""
    try:
        title = HTTPStatus(exc.status_code).phrase
    except ValueError:  # non-standard status code
        title = "HTTP Error"
    problem = build_problem_details(
        status=exc.status_code,
        title=title,
        detail=str(exc.detail) if exc.detail else None,
        error_type=title.lower().replace(" ", "-"),
        instance=str(request.url.path),
    )
    return _problem_response(problem, exc.status_code)


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Map anything unexpected without leaking internals to the client."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    problem = build_problem_details(
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail="An unexpected error occurred while processing the request.",
        error_type="internal-server-error",
        instance=str(request.url.path),
    )
    return _problem_response(problem, HTTPStatus.INTERNAL_SERVER_ERROR)


def register_exception_handlers(app: FastAPI) -> None:
    """Register every global exception handler on the application."""
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
