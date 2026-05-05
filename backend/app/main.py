"""Axiom FastAPI application factory.

Wires up middleware, exception handlers, routers, and the rate limiter.
On startup, seeds the three sample experiments into the database if they are
not already present (idempotent, fails gracefully when DB is unavailable).
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.dependencies import limiter
from app.exceptions import (
    http_exception_handler,
    rate_limit_exceeded_handler,
    request_validation_exception_handler,
    unhandled_exception_handler,
)
from app.middleware import RequestIDMiddleware, SecurityHeadersMiddleware, TimingMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Record startup timestamp and seed sample experiments."""
    app.state.start_time = time.time()

    try:
        from app.data.sample_experiments import seed_sample_experiments
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            await seed_sample_experiments(session)
        logger.info("Sample experiments seeded successfully")
    except Exception as exc:
        # DB may not be available in test/CI environments — never block startup.
        logger.warning("Sample experiment seeding skipped: %s", exc)

    yield


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    app = FastAPI(
        title="Axiom Stats API",
        description=(
            "Stateless stats endpoints for the Axiom A/B testing platform. "
            "Provides sample-size calculation, runtime estimation, and full "
            "experiment analysis (frequentist + optional Bayesian/sequential/CUPED)."
        ),
        version="0.1.0",
        lifespan=_lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── Rate limiter ───────────────────────────────────────────────────────────
    app.state.limiter = limiter

    # ── Exception handlers ─────────────────────────────────────────────────────
    # Registration order matters: more specific types must come before broad ones.
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ── Middleware ─────────────────────────────────────────────────────────────
    # add_middleware() prepends each layer, so the LAST call is the outermost.
    # Execution order for requests: CORS → RequestID → SecurityHeaders → Timing → app
    app.add_middleware(TimingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,  # credentials + wildcard origins is disallowed by spec
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time", "X-RateLimit-Limit",
                        "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    )

    # ── Routers ────────────────────────────────────────────────────────────────
    from app.api.v1.experiments import router as experiments_router
    from app.api.v1.ml import router as ml_router
    from app.api.v1.stats import router as stats_router

    app.include_router(stats_router)
    app.include_router(ml_router)
    app.include_router(experiments_router)

    return app


app = create_app()

