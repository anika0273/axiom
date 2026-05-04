"""
ML analysis orchestrator for A/B experiments.

Runs the four ML modules (anomaly, novelty, HTE, segments) in the most
efficient order, isolates failures, and synthesises results into a single
verdict and set of key insights.

Execution model:
  - Anomaly + novelty run sequentially (fast; use the same daily DataFrame).
  - HTE + segments run in parallel via ThreadPoolExecutor(max_workers=2);
    XGBoost and scikit-learn release the GIL for their C extensions, so
    real wall-clock parallelism is achievable.
  - Any module failure is caught, logged, and recorded — the orchestrator
    never raises from a module exception.

Usage::

    result = run_ml_analysis(MLExperimentInput(
        control_values=ctrl,
        treatment_values=trt,
        user_features=features_df,
        daily_metrics=daily_df,
    ))
    print(result.overall_verdict)   # "CLEAN" | "NEEDS_REVIEW" | "INVALID"
    print(result.recommendation)
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Literal

import numpy as np
import pandas as pd

from app.ml.anomaly import ExperimentValidation, validate_experiment
from app.ml.hte import HTEModel, fit_hte_model
from app.ml.novelty import EffectTrajectory, analyze_effect_trajectory
from app.ml.segments import SegmentAnalysis, discover_segments

logger = logging.getLogger(__name__)

_MIN_USERS_PER_GROUP = 10
_MIN_NOVELTY_DAYS = 7


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ModuleStatus:
    """Execution record for one ML module.

    Attributes:
        module: Machine-readable name — "hte", "segments", "anomaly", "novelty".
        status: "completed" | "skipped" | "failed".
        skip_reason: Human-readable reason when status is "skipped" or "failed".
        duration_seconds: Wall-clock seconds from submit to result.
    """

    module: str
    status: Literal["completed", "skipped", "failed"]
    skip_reason: str | None
    duration_seconds: float


@dataclass
class MLExperimentInput:
    """All data that may be needed by the four ML modules.

    Only control_values and treatment_values are mandatory.  Optional fields
    gate which modules can run: user_features enables HTE and segments;
    daily_metrics enables anomaly and novelty.

    Attributes:
        control_values: Outcome per subject in the control group.
        treatment_values: Outcome per subject in the treatment group.
        user_features: One row per subject (control rows first, then
            treatment rows) with pre-encoded numeric features.  Must have
            len(control_values) + len(treatment_values) rows when provided.
        daily_metrics: Daily experiment data with columns date,
            control_metric, treatment_metric, n_control, n_treatment.
        experiment_start: Experiment start date (informational; not used
            in computations yet).
        feature_names: Optional display names for the feature columns in
            user_features.
    """

    control_values: list[float]
    treatment_values: list[float]
    user_features: pd.DataFrame | None = None
    daily_metrics: pd.DataFrame | None = None
    experiment_start: date | None = None
    feature_names: list[str] | None = None


@dataclass
class MLAnalysisResult:
    """Aggregated output of run_ml_analysis.

    Attributes:
        hte_result: Output of fit_hte_model, or None if skipped/failed.
        segment_result: Output of discover_segments, or None if skipped/failed.
        anomaly_result: Output of validate_experiment, or None if skipped/failed.
        novelty_result: Output of analyze_effect_trajectory, or None if skipped/failed.
        overall_verdict: "CLEAN" | "NEEDS_REVIEW" | "INVALID".
        key_insights: Up to three plain-English findings from completed modules.
        capability_report: One ModuleStatus per module, always four entries.
        can_trust_results: False when anomaly verdict is INVALID.
        recommendation: Standard actionable recommendation string.
    """

    hte_result: HTEModel | None
    segment_result: SegmentAnalysis | None
    anomaly_result: ExperimentValidation | None
    novelty_result: EffectTrajectory | None
    overall_verdict: Literal["CLEAN", "NEEDS_REVIEW", "INVALID"]
    key_insights: list[str]
    capability_report: list[ModuleStatus]
    can_trust_results: bool
    recommendation: str


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_ml_analysis(experiment_data: MLExperimentInput) -> MLAnalysisResult:
    """Run all applicable ML modules and return a unified analysis result.

    Modules are skipped when prerequisite data is absent.  A module that
    raises an unexpected exception is recorded as failed; all other modules
    continue regardless.

    Args:
        experiment_data: Input data bundle.  control_values and
            treatment_values must each have at least 10 observations.

    Returns:
        MLAnalysisResult with verdict, insights, and per-module status.

    Raises:
        ValueError: If either group has fewer than 10 users.
    """
    n_ctrl = len(experiment_data.control_values)
    n_trt = len(experiment_data.treatment_values)

    if n_ctrl < _MIN_USERS_PER_GROUP or n_trt < _MIN_USERS_PER_GROUP:
        raise ValueError(
            f"Minimum {_MIN_USERS_PER_GROUP} users per group required; "
            f"got {n_ctrl} control, {n_trt} treatment."
        )

    statuses: dict[str, ModuleStatus] = {}
    anomaly_result: ExperimentValidation | None = None
    novelty_result: EffectTrajectory | None = None
    hte_result: HTEModel | None = None
    segment_result: SegmentAnalysis | None = None

    # ── Anomaly detection ──────────────────────────────────────────────────
    if experiment_data.daily_metrics is None:
        statuses["anomaly"] = _skipped("anomaly", "No daily time-series data provided")
    else:
        dm = experiment_data.daily_metrics
        status, result = _run_timed("anomaly", lambda: validate_experiment(dm))
        statuses["anomaly"] = status
        anomaly_result = result

    # ── Novelty detection ─────────────────────────────────────────────────
    if experiment_data.daily_metrics is None:
        statuses["novelty"] = _skipped("novelty", "No daily data")
    elif len(experiment_data.daily_metrics) < _MIN_NOVELTY_DAYS:
        statuses["novelty"] = _skipped("novelty", "Fewer than 7 days available")
    else:
        dm = experiment_data.daily_metrics
        daily_lift = pd.Series(
            dm["treatment_metric"].values - dm["control_metric"].values,
            dtype=float,
        )
        # Proxy SE: 1/sqrt(n_total) — gives more weight to high-volume days.
        n_total = dm["n_control"].values.astype(float) + dm["n_treatment"].values.astype(float)
        daily_se = pd.Series(1.0 / np.sqrt(np.maximum(n_total, 1.0)), dtype=float)
        n_days = len(daily_lift)

        status, result = _run_timed(
            "novelty",
            lambda: analyze_effect_trajectory(daily_lift, daily_se, n_days),
        )
        statuses["novelty"] = status
        novelty_result = result

    # ── HTE + segments (parallel) ─────────────────────────────────────────
    if experiment_data.user_features is None:
        statuses["hte"] = _skipped("hte", "No user-level features provided")
        statuses["segments"] = _skipped("segments", "No user-level features provided")
    else:
        X = experiment_data.user_features
        outcome = pd.Series(
            experiment_data.control_values + experiment_data.treatment_values,
            dtype=float,
        )
        treatment = pd.Series(
            [0.0] * n_ctrl + [1.0] * n_trt,
            dtype=float,
        )

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_hte = executor.submit(
                _run_timed, "hte", lambda: fit_hte_model(X, treatment, outcome)
            )
            future_seg = executor.submit(
                _run_timed, "segments", lambda: discover_segments(X, treatment, outcome)
            )
            statuses["hte"], hte_result = future_hte.result()
            statuses["segments"], segment_result = future_seg.result()

    # ── Synthesis ─────────────────────────────────────────────────────────
    capability_report = [
        statuses["anomaly"],
        statuses["novelty"],
        statuses["hte"],
        statuses["segments"],
    ]

    overall_verdict, can_trust, recommendation = _derive_verdict(
        anomaly_result=anomaly_result,
        novelty_result=novelty_result,
        statuses=statuses,
    )

    key_insights = _extract_insights(
        hte=hte_result,
        segments=segment_result,
        anomaly=anomaly_result,
        novelty=novelty_result,
    )

    logger.info(
        "ml_engine finished verdict=%s insights=%d modules_completed=%d",
        overall_verdict,
        len(key_insights),
        sum(1 for s in capability_report if s.status == "completed"),
    )

    return MLAnalysisResult(
        hte_result=hte_result,
        segment_result=segment_result,
        anomaly_result=anomaly_result,
        novelty_result=novelty_result,
        overall_verdict=overall_verdict,
        key_insights=key_insights,
        capability_report=capability_report,
        can_trust_results=can_trust,
        recommendation=recommendation,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_timed(
    name: str,
    fn: Callable[[], Any],
) -> tuple[ModuleStatus, Any]:
    """Call fn(), measuring wall-clock time.  Returns (ModuleStatus, result).

    Catches all exceptions so the caller's orchestration loop is never
    interrupted by a module failure.
    """
    logger.info("module %s starting", name)
    start = time.perf_counter()
    try:
        result = fn()
        duration = time.perf_counter() - start
        logger.info("module %s completed in %.3fs", name, duration)
        return ModuleStatus(name, "completed", None, duration), result
    except Exception as exc:
        duration = time.perf_counter() - start
        logger.error(
            "module %s failed after %.3fs: %s", name, duration, exc, exc_info=True
        )
        return ModuleStatus(name, "failed", str(exc), duration), None


def _skipped(name: str, reason: str) -> ModuleStatus:
    return ModuleStatus(name, "skipped", reason, 0.0)


def _derive_verdict(
    anomaly_result: ExperimentValidation | None,
    novelty_result: EffectTrajectory | None,
    statuses: dict[str, ModuleStatus],
) -> tuple[Literal["CLEAN", "NEEDS_REVIEW", "INVALID"], bool, str]:
    """Derive overall_verdict, can_trust_results, and recommendation."""
    # INVALID: anomaly module ran and flagged critical data problems.
    if anomaly_result is not None and not anomaly_result.can_trust_results:
        return (
            "INVALID",
            False,
            "Do not act on these results. Data integrity issues detected.",
        )

    any_failed = any(s.status == "failed" for s in statuses.values())
    all_non_completed = all(s.status != "completed" for s in statuses.values())

    # NEEDS_REVIEW: warning from anomaly, novelty decay, or unexpected failure.
    if (
        (anomaly_result is not None and anomaly_result.overall_validity == "WARNING")
        or (novelty_result is not None and novelty_result.pattern == "NOVELTY")
        or any_failed
        or all_non_completed
    ):
        if all_non_completed:
            return (
                "NEEDS_REVIEW",
                True,
                "Insufficient data for ML analysis. Provide user features and daily metrics.",
            )
        return (
            "NEEDS_REVIEW",
            True,
            "Results need review. Check flagged issues before acting.",
        )

    return (
        "CLEAN",
        True,
        "Results are reliable. Proceed with shipping decision.",
    )


def _extract_insights(
    hte: HTEModel | None,
    segments: SegmentAnalysis | None,
    anomaly: ExperimentValidation | None,
    novelty: EffectTrajectory | None,
) -> list[str]:
    """Return up to 3 plain-English insights from completed modules.

    Priority order: anomaly → novelty → HTE → segments.
    Skipped or failed modules contribute no placeholder.
    """
    insights: list[str] = []

    # Anomaly: most critical — data integrity comes first.
    if anomaly is not None:
        failed = [c for c in anomaly.checks if not c.passed]
        if failed:
            names = ", ".join(c.name for c in failed)
            insights.append(
                f"Data quality issues detected ({names}). "
                f"Validity: {anomaly.overall_validity}."
            )
        else:
            insights.append(
                "Data quality checks passed — all four validity checks are clean."
            )

    # Novelty: timing matters before any targeting decision.
    if novelty is not None and len(insights) < 3:
        insights.append(novelty.recommendation)

    # HTE: most actionable for targeting.
    if hte is not None and len(insights) < 3:
        if hte.top_interactions:
            feat = hte.top_interactions[0].replace("_x_treat", "")
            insights.append(
                f"Strongest treatment modifier: {feat} "
                f"(ATE={hte.ate:+.4f}, stability={hte.stability_score:.2f}). "
                + hte.business_recommendation
            )
        else:
            insights.append(
                f"HTE analysis complete. ATE={hte.ate:+.4f}, "
                f"stability={hte.stability_score:.2f}. "
                + hte.business_recommendation
            )

    # Segments: audience discovery.
    if segments is not None and len(insights) < 3:
        if segments.responsive_segments:
            top_id = segments.responsive_segments[0]
            top_seg = next((s for s in segments.segments if s.id == top_id), None)
            if top_seg:
                insights.append(
                    f"Segment {top_id} ({top_seg.size_pct:.0%} of users) shows "
                    f"strongest response (lift={top_seg.lift:+.4f}). "
                    + segments.overall_recommendation
                )
            else:
                insights.append(
                    f"{len(segments.responsive_segments)} responsive segment(s) "
                    f"found across {segments.optimal_k} clusters. "
                    + segments.overall_recommendation
                )
        else:
            insights.append(
                f"{segments.optimal_k} segments found; no segment shows "
                f"significantly stronger response. "
                + segments.overall_recommendation
            )

    return insights
