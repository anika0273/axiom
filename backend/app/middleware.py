"""ASGI middleware for Axiom: request tracing, timing, and security headers.

Middleware add order in main.py determines execution order.  The last
middleware added wraps all the others (outermost on request, innermost on
response).  Intended stack (outer → inner):

  CORS → RequestID → SecurityHeaders → Timing → app
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assign a UUID to every request for distributed tracing.

    Reads X-Request-ID from the incoming request headers; generates a fresh
    UUID if absent.  Stores the ID on request.state.request_id and echoes it
    back in the X-Request-ID response header.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status code, and wall-clock duration for every request.

    Emits a structured INFO log entry after the response is fully produced.
    Also injects X-Response-Time (milliseconds) into every response header.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0
        request_id = getattr(request.state, "request_id", "unknown")
        logger.info(
            "%s %s %d %.1fms req=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject OWASP-recommended security headers on every response."""

    _HEADERS: dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
    }

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        response: Response = await call_next(request)
        for key, value in self._HEADERS.items():
            response.headers[key] = value
        return response
