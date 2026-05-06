"""Guaranteed-safe fallback responses for all three intelligence modules.

All fallbacks:
  - Clearly indicate they are template-based (never masquerade as AI output).
  - Use actual values from stats_result / ml_result — never invent numbers.
  - Are synchronous and have no I/O, so they cannot fail.

Exports:
    fallback_plan            — ExperimentPlanResult with clarifying questions
    fallback_interpretation  — grounded plain-English interpretation string
    fallback_report          — StakeholderReport from templates, no Claude API
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.intelligence.interpreter import FullAnalysisResult, MLAnalysisSummary
    from app.intelligence.reporter import StakeholderReport

# Standard clarifying questions asked when the AI is unavailable and the
# description is too vague to plan deterministically.
_STANDARD_QUESTIONS: list[str] = [
    "What is the current baseline conversion rate or metric value for this experiment?",
    "How many eligible users or sessions do you see per day?",
    "What minimum improvement (MDE) would make this experiment worth running?",
    "What type of metric are you measuring — proportion/binary, continuous mean, or ratio?",
    "How many days can you run the experiment?",
    "What guardrail metrics should we monitor for unintended regressions?",
]

_FALLBACK_NOTE = "[Auto-generated — AI unavailable]"


# ─────────────────────────────────────────────────────────────────────────────
# fallback_plan
# ─────────────────────────────────────────────────────────────────────────────


def fallback_plan(description: str) -> dict[str, Any]:
    """Return a safe needs_clarification response when the planner Claude call fails.

    Never invents a plan. Instead surfaces the standard set of questions that
    must be answered before a valid plan can be produced.

    Args:
        description: The original experiment description (used only for logging;
                     not included in the returned dict to avoid leaking raw input).

    Returns:
        Dict compatible with ExperimentPlanResult fields:
        needs_clarification=True, clarifying_questions populated, confidence=low.
    """
    return {
        "needs_clarification": True,
        "clarifying_questions": _STANDARD_QUESTIONS,
        "confidence": "low",
        "confidence_reasoning": (
            f"{_FALLBACK_NOTE} AI unavailable — provide the answers below "
            "and resubmit to generate a full experiment plan."
        ),
        "plan": None,
        "stats_engine_verification": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# fallback_interpretation
# ─────────────────────────────────────────────────────────────────────────────


def fallback_interpretation(
    stats_result: "FullAnalysisResult",
    ml_result: "MLAnalysisSummary",
) -> str:
    """Build a grounded interpretation string when the Claude stream fails.

    Uses actual statistical values — never fabricates numbers or findings.
    Clearly labelled as auto-generated.

    Args:
        stats_result: Statistical analysis output.
        ml_result: ML analysis summary.

    Returns:
        Multi-sentence plain-English interpretation string.
    """
    # Delegate to the existing template which is already grounded and tested.
    from app.intelligence.templates.fallback_interpretation import (
        build_fallback_interpretation,
    )

    body = build_fallback_interpretation(stats_result, ml_result)
    return f"{_FALLBACK_NOTE}\n\n{body}"


# ─────────────────────────────────────────────────────────────────────────────
# fallback_report
# ─────────────────────────────────────────────────────────────────────────────


def fallback_report(
    stats_result: "FullAnalysisResult",
    ml_result: "MLAnalysisSummary",
    experiment_name: str,
    daily_traffic: int | None = None,
    daily_revenue: float | None = None,
) -> "StakeholderReport":
    """Build a complete 8-section stakeholder report without any Claude API call.

    All sections 1–7 are template-based and labelled as auto-generated.
    Section 8 (Technical Appendix) is always programmatic anyway.

    Args:
        stats_result: Statistical analysis output.
        ml_result: ML analysis summary.
        experiment_name: Human-readable experiment name.
        daily_traffic: Optional daily user count.
        daily_revenue: Optional daily revenue for business impact calculation.

    Returns:
        StakeholderReport with prompt_version ending in '_fallback'.
    """
    # Lazy import to avoid circular dependency (reporter imports fallbacks at
    # runtime for nothing; fallbacks imports reporter only here).
    from app.intelligence.reporter import build_fallback_report as _build

    return _build(
        experiment_name=experiment_name,
        stats_result=stats_result,
        ml_result=ml_result,
        daily_traffic=daily_traffic,
        daily_revenue=daily_revenue,
    )
