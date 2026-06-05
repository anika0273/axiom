"""Claude-powered experiment result interpreter.

Converts statistical and ML analysis output into plain-English interpretations
streamed word-by-word to the frontend via Server-Sent Events.

All interpretations are grounded in the actual statistical values passed in —
Claude is explicitly instructed never to fabricate lift percentages or findings.

Exports:
    FullAnalysisResult    — lightweight stats result model for the interpreter
    MLAnalysisSummary     — lightweight ML result model for the interpreter
    interpret_results     — async generator: streams Claude interpretation
    interpret_subgroup    — non-streaming: one-shot segment interpretation
    build_fallback_interpretation — template-based fallback (no Claude needed)
    parse_stats_from_json — hydrate FullAnalysisResult from DB JSON
    parse_ml_from_json    — hydrate MLAnalysisSummary from DB JSON
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic

from app.core.config import settings
from app.intelligence.guardrails import InputGuardrail, OutputValidator
from app.intelligence.templates.fallback_interpretation import (
    build_fallback_interpretation,
)

_output_validator = OutputValidator()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROMPT_VERSION = "interpreter_v1"
CLAUDE_MODEL = "claude-sonnet-4-6"
TIMEOUT_SECONDS = 45.0
MAX_OUTPUT_TOKENS = 512

_COST_PER_INPUT_TOKEN = 3.0 / 1_000_000
_COST_PER_OUTPUT_TOKEN = 15.0 / 1_000_000

_SYSTEM_PROMPT: str = (
    Path(__file__).parent / "prompts" / "interpreter_v1.txt"
).read_text(encoding="utf-8")

_SUBGROUP_SYSTEM = (
    "You are a senior data scientist. Write brief, direct segment interpretations "
    "for product teams. Use declarative language for significant segments. "
    "Avoid filler. Maximum 60 words."
)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class FullAnalysisResult:
    """Lightweight stats result for the interpreter layer.

    Populated from either the stats engine output or deserialized DB JSON.

    Attributes:
        is_significant: Whether the primary result passes the significance test.
        p_value: Observed p-value from the hypothesis test.
        lift_pct: Relative lift in percent (e.g. 31.4 means +31.4%).
        lift_abs: Absolute lift (treatment metric minus control metric).
        overall_recommendation: Engine recommendation: RUN/STOP_WIN/STOP_LOSE/NO_EFFECT.
        warnings: Non-fatal data quality warnings from the stats pipeline.
        plain_english: Engine-generated plain-English summary (may be empty).
    """

    is_significant: bool
    p_value: float
    lift_pct: float
    lift_abs: float
    overall_recommendation: str
    warnings: list[str] = field(default_factory=list)
    plain_english: str = ""


@dataclass
class MLAnalysisSummary:
    """Lightweight ML analysis summary for the interpreter layer.

    Attributes:
        overall_verdict: CLEAN | NEEDS_REVIEW | INVALID.
        can_trust_results: False when anomaly detection flagged critical issues.
        key_insights: Up to three plain-English insights from completed ML modules.
        recommendation: Actionable recommendation string from the ML engine.
        anomaly_validity: VALID | WARNING | INVALID, or None if module skipped.
        novelty_pattern: STABLE | NOVELTY | LEARNING | INSUFFICIENT, or None.
        hte_top_modifier: Feature name of the strongest treatment modifier, or None.
        hte_ate: Average treatment effect from the HTE model, or None.
        hte_business_recommendation: Business recommendation from the HTE module.
        responsive_segments: List of segment IDs with above-average response, or None.
        segment_recommendation: Overall rollout recommendation from the segments module.
    """

    overall_verdict: str
    can_trust_results: bool
    key_insights: list[str] = field(default_factory=list)
    recommendation: str = ""
    anomaly_validity: str | None = None
    novelty_pattern: str | None = None
    hte_top_modifier: str | None = None
    hte_ate: float | None = None
    hte_business_recommendation: str | None = None
    responsive_segments: list[int] | None = None
    segment_recommendation: str | None = None


# Re-export for callers that import build_fallback_interpretation from here.
__all__ = [
    "FullAnalysisResult",
    "MLAnalysisSummary",
    "build_fallback_interpretation",
    "interpret_results",
    "interpret_subgroup",
    "parse_stats_from_json",
    "parse_ml_from_json",
    "PROMPT_VERSION",
]

# ---------------------------------------------------------------------------
# JSON hydration helpers
# ---------------------------------------------------------------------------


def parse_stats_from_json(json_data: dict[str, Any]) -> FullAnalysisResult:
    """Build a FullAnalysisResult from full_analysis_json stored in the DB.

    Handles two layouts:
      - Nested: {"stats_result": {"primary_result": {...}, ...}, "ml_result": {...}}
      - Flat ML-only: {"overall_verdict": ..., ...}  (falls back gracefully)

    Args:
        json_data: Raw dict from ExperimentResult.full_analysis_json.

    Returns:
        FullAnalysisResult populated from the best-available data.
    """
    stats = json_data.get("stats_result", {})
    primary = stats.get("primary_result", {})

    return FullAnalysisResult(
        is_significant=bool(primary.get("is_significant", False)),
        p_value=float(primary.get("p_value", 1.0)),
        lift_pct=float(primary.get("lift_pct", 0.0)),
        lift_abs=float(primary.get("lift_abs", 0.0)),
        overall_recommendation=str(stats.get("overall_recommendation", "RUN")),
        warnings=list(stats.get("warnings", [])),
        plain_english=str(stats.get("plain_english", "")),
    )


def parse_ml_from_json(json_data: dict[str, Any]) -> MLAnalysisSummary:
    """Build an MLAnalysisSummary from full_analysis_json stored in the DB.

    Handles two layouts:
      - Nested: {"ml_result": {...}, "stats_result": {...}}
      - Flat (legacy): {"overall_verdict": ..., "hte": {...}, ...}

    Args:
        json_data: Raw dict from ExperimentResult.full_analysis_json.

    Returns:
        MLAnalysisSummary populated from available ML fields.
    """
    ml = json_data.get("ml_result", json_data)

    anomaly: dict[str, Any] = ml.get("anomaly") or {}
    novelty: dict[str, Any] = ml.get("novelty") or {}
    hte: dict[str, Any] = ml.get("hte") or {}
    segments: dict[str, Any] = ml.get("segments") or {}

    top_interactions: list[str] = hte.get("top_interactions") or []
    hte_top = top_interactions[0] if top_interactions else None

    responsive: list[int] | None = None
    if segments:
        raw_resp = segments.get("responsive_segments")
        responsive = list(raw_resp) if raw_resp is not None else []

    return MLAnalysisSummary(
        overall_verdict=str(ml.get("overall_verdict", "NEEDS_REVIEW")),
        can_trust_results=bool(ml.get("can_trust_results", True)),
        key_insights=list(ml.get("key_insights") or []),
        recommendation=str(ml.get("recommendation", "")),
        anomaly_validity=str(anomaly["overall_validity"]) if anomaly else None,
        novelty_pattern=str(novelty["pattern"]) if novelty else None,
        hte_top_modifier=hte_top,
        hte_ate=float(hte["ate"]) if hte else None,
        hte_business_recommendation=hte.get("business_recommendation") if hte else None,
        responsive_segments=responsive,
        segment_recommendation=(
            segments.get("overall_recommendation") if segments else None
        ),
    )


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _build_user_prompt(
    stats: FullAnalysisResult,
    ml: MLAnalysisSummary,
    experiment_name: str,
    daily_traffic: int | None,
) -> str:
    """Construct the grounded user prompt sent to Claude.

    All numerical values are injected explicitly so Claude never needs to
    invent or estimate any figure.
    """
    lines: list[str] = [
        f"Experiment: {experiment_name}",
        "",
        "=== DATA SECTION (use these values exactly — do not invent other numbers) ===",
        "",
        "STATISTICAL RESULTS:",
        f"  is_significant: {stats.is_significant}",
        f"  p_value: {stats.p_value:.6f}",
        f"  lift_pct (relative lift): {stats.lift_pct:+.4f}%",
        f"  lift_abs (absolute lift): {stats.lift_abs:+.6f}",
        f"  overall_recommendation: {stats.overall_recommendation}",
    ]

    if stats.warnings:
        lines.append(f"  warnings: {'; '.join(stats.warnings)}")

    lines += [
        "",
        "ML VALIDITY:",
        f"  overall_verdict: {ml.overall_verdict}",
        f"  can_trust_results: {ml.can_trust_results}",
    ]

    if ml.anomaly_validity:
        lines.append(f"  anomaly_validity: {ml.anomaly_validity}")
    if ml.novelty_pattern:
        lines.append(f"  novelty_pattern: {ml.novelty_pattern}")

    if ml.hte_top_modifier:
        modifier_clean = ml.hte_top_modifier.replace("_x_treat", "")
        lines.append(f"  hte_top_modifier: {modifier_clean}")
        if ml.hte_ate is not None:
            lines.append(f"  hte_ate: {ml.hte_ate:+.4f}")
        if ml.hte_business_recommendation:
            lines.append(f"  hte_recommendation: {ml.hte_business_recommendation}")

    if ml.responsive_segments is not None:
        lines.append(f"  responsive_segments: {ml.responsive_segments}")
    if ml.segment_recommendation:
        lines.append(f"  segment_recommendation: {ml.segment_recommendation}")

    if ml.key_insights:
        lines += ["", "KEY INSIGHTS FROM ML ENGINE:"]
        for insight in ml.key_insights:
            lines.append(f"  - {insight}")

    if daily_traffic:
        lines += ["", f"CONTEXT: daily_traffic = {daily_traffic} users/day"]

    lines += [
        "",
        "=== END DATA SECTION ===",
        "",
        "Write the interpretation following the structure in your instructions. "
        "Maximum 250 words. Use the exact lift_pct value above — do not round to a different number.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Grounding validator
# ---------------------------------------------------------------------------


def _validate_grounding(assembled: str, stats: FullAnalysisResult) -> None:
    """Log warnings when Claude's output may have drifted from the actual data.

    Checks:
      1. Any percentage mentioned that differs by more than 2pp from lift_pct.
      2. "SHIP" recommended when is_significant=False.
    """
    lower = assembled.lower()

    # Check for SHIP when not significant
    if not stats.is_significant:
        # "ship" outside of "do_not_ship" / "not ship" context is a grounding failure
        ship_pos = lower.find("ship")
        while ship_pos != -1:
            context = lower[max(0, ship_pos - 10) : ship_pos + 15]
            if (
                "not" not in context
                and "do_not" not in context
                and "do not" not in context
            ):
                logger.warning(
                    "grounding: 'ship' found for non-significant result (p=%.4f) context=%r",
                    stats.p_value,
                    context,
                )
                break
            ship_pos = lower.find("ship", ship_pos + 1)

    # Check lift percentage mentions
    expected = abs(stats.lift_pct)
    for pct_str in re.findall(r"(\d+\.?\d*)%", assembled):
        val = float(pct_str)
        if val > 1.0 and abs(val - expected) > 2.0:
            logger.warning(
                "grounding: %.1f%% mentioned but expected lift is %.4f%%",
                val,
                stats.lift_pct,
            )


# ---------------------------------------------------------------------------
# Core streaming function
# ---------------------------------------------------------------------------


async def interpret_results(
    stats_result: FullAnalysisResult,
    ml_result: MLAnalysisSummary,
    experiment_name: str,
    daily_traffic: int | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a Claude-generated interpretation of experiment results.

    Yields text chunks as they arrive from the Claude API (typically word by word).
    The user prompt is constructed from the actual statistical values — Claude is
    instructed to use only those values and never fabricate figures.

    After the stream completes, runs a grounding validator and OutputValidator.
    If the stream fails at any point, yields the template-based fallback instead.

    Args:
        stats_result: Statistical analysis output with significance, lift, p-value, etc.
        ml_result: ML analysis summary with validity verdict, segment data, and HTE.
        experiment_name: Human-readable experiment name included in the prompt.
        daily_traffic: Optional daily traffic estimate for context (not used statistically).

    Yields:
        Text chunks from the Claude streaming response, or fallback text on failure.
    """
    # Sanitize experiment_name before including it in the prompt
    sanitized = InputGuardrail.sanitize(experiment_name, max_chars=200)
    safe_name = (
        sanitized.text if not sanitized.rejection_reason else "Unnamed Experiment"
    )
    if sanitized.rejection_reason:
        logger.warning(
            "interpret_results: experiment_name rejected by guardrail: %s",
            sanitized.rejection_reason,
        )

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    user_prompt = _build_user_prompt(stats_result, ml_result, safe_name, daily_traffic)

    assembled: list[str] = []
    t0 = time.monotonic()

    try:
        async with client.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            timeout=TIMEOUT_SECONDS,
        ) as stream:
            async for text in stream.text_stream:
                assembled.append(text)
                yield text

            try:
                final = await stream.get_final_message()
                duration_s = time.monotonic() - t0
                cost = (
                    final.usage.input_tokens * _COST_PER_INPUT_TOKEN
                    + final.usage.output_tokens * _COST_PER_OUTPUT_TOKEN
                )
                logger.info(
                    "interpreter stream complete experiment=%r tokens_in=%d tokens_out=%d "
                    "duration_s=%.2f cost_usd=%.5f prompt_version=%s",
                    safe_name,
                    final.usage.input_tokens,
                    final.usage.output_tokens,
                    duration_s,
                    cost,
                    PROMPT_VERSION,
                )
            except Exception as exc:
                logger.warning("failed to get final message from stream: %s", exc)

        # Post-stream grounding and output validation
        full_text = "".join(assembled)
        if full_text:
            _validate_grounding(full_text, stats_result)
            stats_dict = {
                "is_significant": stats_result.is_significant,
                "lift_pct": stats_result.lift_pct,
            }
            report = _output_validator.validate_interpretation(full_text, stats_dict)
            if report.issues:
                logger.warning(
                    "interpreter OutputValidator found %d issue(s) for experiment=%r: %s",
                    len(report.issues),
                    safe_name,
                    [i.message for i in report.issues],
                )

    except Exception as exc:
        logger.warning(
            "interpret_results: stream failed for experiment=%r — yielding fallback: %s",
            safe_name,
            exc,
        )
        # If we already yielded some text the stream is broken mid-way;
        # emit a clear separator then the full fallback.
        if assembled:
            yield "\n\n[AI interpretation incomplete — switching to template]\n\n"
        else:
            yield "[AI interpretation unavailable — template-based summary below]\n\n"
        fallback_text = build_fallback_interpretation(stats_result, ml_result)
        yield fallback_text


# ---------------------------------------------------------------------------
# Non-streaming subgroup interpretation
# ---------------------------------------------------------------------------


async def interpret_subgroup(
    segment_profile: dict[str, Any],
    experiment_name: str,
) -> str:
    """Return a short plain-English interpretation of a single user segment.

    Non-streaming, returns the full response as a string. Used for on-demand
    segment detail views in the frontend.

    Args:
        segment_profile: Segment data dict with keys such as id, size_pct, lift,
                         significant, description, and top_features.
        experiment_name: Experiment name for context.

    Returns:
        A 2-3 sentence interpretation string, or an empty string on API failure.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    size_pct = segment_profile.get("size_pct", 0.0)
    lift = segment_profile.get("lift", 0.0)
    significant = segment_profile.get("significant", False)
    description = segment_profile.get("description", "N/A")
    seg_id = segment_profile.get("id", "unknown")

    prompt = (
        f"Experiment: {experiment_name}\n\n"
        f"Segment {seg_id} profile:\n"
        f"  size: {size_pct:.1%} of users\n"
        f"  lift: {lift:+.4f}\n"
        f"  significant: {significant}\n"
        f"  description: {description}\n\n"
        "Write 2-3 sentences explaining what this segment means for the product team. "
        "Be specific about the lift value. Use declarative language if significant=True."
    )

    try:
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=120,
            system=_SUBGROUP_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            timeout=15.0,
        )
        return response.content[0].text if response.content else ""
    except Exception as exc:
        logger.warning(
            "interpret_subgroup failed for experiment=%r: %s", experiment_name, exc
        )
        direction = "increased" if lift > 0 else "decreased"
        return (
            f"Segment {seg_id} ({size_pct:.1%} of users) {direction} "
            f"the primary metric by {abs(lift):.4f} "
            f"({'significant' if significant else 'not significant'})."
        )
