"""Fixtures for intelligence integration tests.

All tests in this directory hit the real Claude API and a real PostgreSQL
database.  Run them explicitly:
    pytest -m integration backend/tests/integration/

The db_session fixture creates a fresh SQLAlchemy engine per test so that
the async engine is always bound to the running test's event loop — avoids
the classic asyncpg "attached to a different loop" error when pytest-asyncio
assigns each test a new event loop (STRICT mode, function scope).
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.intelligence.interpreter import (
    FullAnalysisResult,
    MLAnalysisSummary,
    parse_ml_from_json,
    parse_stats_from_json,
)
from app.models.experiment import AIInteraction

# ---------------------------------------------------------------------------
# Integration DB URL — overridable via environment variable.
# Default points to the Docker PostgreSQL exposed on localhost:5434.
# In GitHub Actions the workflow sets INTEGRATION_DB_URL to the service URL.
# ---------------------------------------------------------------------------

INTEGRATION_DB_URL: str = os.environ.get(
    "INTEGRATION_DB_URL",
    "postgresql+asyncpg://axiom:changeme@localhost:5434/axiom",
)


@pytest.fixture
def require_real_api_key() -> None:
    """Skip the test when ANTHROPIC_API_KEY is absent or a placeholder."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key.startswith("sk-ant-"):
        pytest.skip("Real ANTHROPIC_API_KEY required — set it to run live AI tests")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SAMPLES_DIR = Path(__file__).parents[2] / "app" / "data" / "samples"

# ---------------------------------------------------------------------------
# DB fixture
#
# Engine is created INSIDE the fixture so it is always bound to the test's
# event loop (pytest-asyncio STRICT mode gives each test its own loop).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession for the integration database.

    Creates and disposes the engine within the test's own event loop.
    Rolls back all changes after the test so sessions are isolated.
    """
    engine = create_async_engine(INTEGRATION_DB_URL, pool_pre_ping=True, echo=False)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


# ---------------------------------------------------------------------------
# Shared helpers — imported by test module
# ---------------------------------------------------------------------------


async def count_ai_interactions(session: AsyncSession) -> int:
    """Return the current ai_interactions row count visible in the open transaction."""
    result = await session.execute(select(func.count()).select_from(AIInteraction))
    return result.scalar_one()


async def _retry_once(coro_fn) -> Any:
    """Run coro_fn; on AssertionError wait 2 s and retry exactly once."""
    for attempt in (1, 2):
        try:
            return await coro_fn()
        except AssertionError:
            if attempt == 2:
                raise
            await asyncio.sleep(2)


# ---------------------------------------------------------------------------
# Sample data fixtures (session-scoped — JSON load is cheap and idempotent)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def saas_result() -> dict[str, Any]:
    """SaaS trial — CLEAN, SIGNIFICANT, STABLE."""
    data = json.loads((SAMPLES_DIR / "saas_trial.json").read_text())
    return data["precomputed_result"]


@pytest.fixture(scope="session")
def ecommerce_result() -> dict[str, Any]:
    """E-commerce checkout — INVALID (SRM detected, can_trust_results=False)."""
    data = json.loads((SAMPLES_DIR / "ecommerce_checkout.json").read_text())
    return data["precomputed_result"]


@pytest.fixture(scope="session")
def marketplace_result() -> dict[str, Any]:
    """Marketplace fee — NEEDS_REVIEW, anomaly WARNING, not significant."""
    data = json.loads((SAMPLES_DIR / "marketplace_fee.json").read_text())
    return data["precomputed_result"]


@pytest.fixture(scope="session")
def saas_stats(saas_result: dict[str, Any]) -> FullAnalysisResult:
    return parse_stats_from_json(saas_result)


@pytest.fixture(scope="session")
def saas_ml(saas_result: dict[str, Any]) -> MLAnalysisSummary:
    return parse_ml_from_json(saas_result)


@pytest.fixture(scope="session")
def ecommerce_stats(ecommerce_result: dict[str, Any]) -> FullAnalysisResult:
    return parse_stats_from_json(ecommerce_result)


@pytest.fixture(scope="session")
def ecommerce_ml(ecommerce_result: dict[str, Any]) -> MLAnalysisSummary:
    return parse_ml_from_json(ecommerce_result)


@pytest.fixture(scope="session")
def marketplace_stats(marketplace_result: dict[str, Any]) -> FullAnalysisResult:
    return parse_stats_from_json(marketplace_result)


@pytest.fixture(scope="session")
def marketplace_ml(marketplace_result: dict[str, Any]) -> MLAnalysisSummary:
    return parse_ml_from_json(marketplace_result)
