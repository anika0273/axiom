"""Custom exception types and global exception handlers for Axiom.

All handlers return responses in the standard error envelope:
  { "error": { "code": "...", "message": "...", "details": {} } }

Services raise ValueError or typed exceptions; the API layer (here) converts
them to HTTP responses. Stack traces are never sent to clients.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def _error_envelope(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


_HTTP_CODE_MAP: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "UNPROCESSABLE",
    429: "RATE_LIMITED",
}


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return 422 with field-level error detail in the standard envelope."""
    field_errors = [
        {
            "field": ".".join(str(loc) for loc in err["loc"]),
            "message": err["msg"],
            "type": err["type"],
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=_error_envelope(
            "VALIDATION_ERROR",
            "Request body validation failed.",
            {"fields": field_errors},
        ),
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Map Starlette HTTP exceptions to the standard error envelope."""
    code = _HTTP_CODE_MAP.get(exc.status_code, f"HTTP_{exc.status_code}")
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_envelope(code, str(exc.detail)),
    )


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    """Return 429 with the rate-limit detail in the standard envelope."""
    return JSONResponse(
        status_code=429,
        content=_error_envelope(
            "RATE_LIMITED",
            f"Rate limit exceeded: {exc.detail}",
        ),
        headers={"Retry-After": "60"},
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Catch-all: log full traceback internally, return a safe 500 body."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        "Unhandled exception request_id=%s path=%s: %s",
        request_id,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content=_error_envelope("INTERNAL_ERROR", "An unexpected error occurred."),
    )
