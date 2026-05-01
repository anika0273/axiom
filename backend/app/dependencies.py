"""FastAPI dependency providers and the slowapi rate limiter for Axiom."""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.stats.engine import (
    ExperimentAnalysis,
    ExperimentConfig,
    ExperimentData,
    analyze_experiment,
)
from app.stats.power import (
    RuntimeEstimate,
    SampleSizeResult,
    calculate_sample_size,
    runtime_estimate,
)

# ── Rate limiter ───────────────────────────────────────────────────────────────
# Keyed on remote IP address.  The app registers this on app.state in main.py.
limiter: Limiter = Limiter(key_func=get_remote_address, headers_enabled=True)


# ── Stats engine ───────────────────────────────────────────────────────────────


class StatsEngine:
    """Thin wrapper around the stats functions enabling Depends() injection.

    Wrapping the functions in a class makes it easy to swap a mock in tests
    via app.dependency_overrides[get_stats_engine].
    """

    def compute_sample_size(
        self,
        baseline_rate: float,
        mde: float,
        alpha: float = 0.05,
        power: float = 0.80,
    ) -> SampleSizeResult:
        """Calculate required per-group sample size."""
        return calculate_sample_size(baseline_rate, mde, alpha, power)

    def compute_runtime(
        self,
        required_sample_size: int,
        daily_traffic: int,
    ) -> RuntimeEstimate:
        """Estimate experiment duration in days/weeks."""
        return runtime_estimate(required_sample_size, daily_traffic)

    def analyze(
        self,
        config: ExperimentConfig,
        data: ExperimentData,
        current_look: int | None = None,
    ) -> ExperimentAnalysis:
        """Run the full six-stage stats pipeline."""
        return analyze_experiment(config, data, current_look)


def get_stats_engine() -> StatsEngine:
    """Provide a StatsEngine instance; override in tests for mocking."""
    return StatsEngine()


def get_request_id(request: Request) -> str:
    """Extract the request ID set by RequestIDMiddleware."""
    return getattr(request.state, "request_id", "unknown")
