"""Template-based fallback interpretation — no Claude API required.

Called when the Claude stream fails or times out. Produces a valid, grounded
interpretation for any combination of FullAnalysisResult and MLAnalysisSummary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.intelligence.interpreter import FullAnalysisResult, MLAnalysisSummary


def build_fallback_interpretation(
    stats_result: "FullAnalysisResult",
    ml_result: "MLAnalysisSummary",
) -> str:
    """Build a template-based interpretation grounded in the actual result values.

    Covers all combinations of significance and ML validity without any Claude call.
    Safe to call synchronously — no I/O.

    Args:
        stats_result: Statistical analysis result (significance, lift, p-value, etc.).
        ml_result: ML analysis summary (verdict, validity, segment data).

    Returns:
        Multi-paragraph plain-English interpretation string.
    """
    return "\n\n".join([
        _headline(stats_result),
        _validity(stats_result, ml_result),
        _who_it_worked_for(ml_result),
        _recommendation(stats_result, ml_result),
        _unknowns(stats_result, ml_result),
    ])


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _headline(stats: "FullAnalysisResult") -> str:
    direction = "increased" if stats.lift_pct > 0 else "decreased"
    abs_lift = abs(stats.lift_pct)

    if stats.is_significant:
        return (
            f"The treatment {direction} the primary metric by {abs_lift:.1f}% "
            f"(p={stats.p_value:.4f}) — a statistically significant result."
        )
    return (
        f"The treatment did not produce a statistically significant effect "
        f"(observed lift: {stats.lift_pct:+.1f}%, p={stats.p_value:.4f})."
    )


def _validity(stats: "FullAnalysisResult", ml: "MLAnalysisSummary") -> str:
    if not ml.can_trust_results:
        issue = (
            f"anomaly check: {ml.anomaly_validity}"
            if ml.anomaly_validity and ml.anomaly_validity != "VALID"
            else "data integrity issues"
        )
        return (
            f"The results cannot be trusted due to {issue}. "
            "Do not act on this experiment until the underlying data problem is resolved."
        )

    if ml.anomaly_validity and ml.anomaly_validity == "WARNING":
        return (
            "Data quality warnings were raised during validation. "
            "Review the anomaly check details before making a shipping decision. "
            "Results should be treated with caution."
        )

    if ml.novelty_pattern == "NOVELTY":
        return (
            "A novelty effect was detected: the observed lift appears to be driven by "
            "users' initial excitement rather than genuine long-term value. "
            "Extend the experiment to observe steady-state performance before deciding."
        )

    if ml.novelty_pattern == "LEARNING":
        return (
            "A learning curve was detected: the effect is still growing as users adopt "
            "the treatment. Extend the experiment until the lift stabilises before deciding."
        )

    warnings_note = ""
    if stats.warnings:
        warnings_note = f" Note: {stats.warnings[0]}"
    return f"No data integrity issues were detected. The experiment ran cleanly.{warnings_note}"


def _who_it_worked_for(ml: "MLAnalysisSummary") -> str:
    if ml.hte_top_modifier:
        modifier_clean = ml.hte_top_modifier.replace("_x_treat", "")
        ate_str = f" (ATE={ml.hte_ate:+.4f})" if ml.hte_ate is not None else ""
        rec = f" {ml.hte_business_recommendation}" if ml.hte_business_recommendation else ""
        return (
            f"The strongest treatment modifier was {modifier_clean}{ate_str}. "
            f"Treatment effects varied meaningfully across this dimension.{rec}"
        )

    if ml.responsive_segments:
        n = len(ml.responsive_segments)
        seg_rec = f" {ml.segment_recommendation}" if ml.segment_recommendation else ""
        return (
            f"{n} segment(s) showed an above-average response to the treatment. "
            f"Consider a targeted rollout to these groups.{seg_rec}"
        )

    return "Segment analysis was not run for this experiment."


def _recommendation(stats: "FullAnalysisResult", ml: "MLAnalysisSummary") -> str:
    if not ml.can_trust_results:
        return (
            "INVESTIGATE: Resolve the data integrity issue before making any shipping decision. "
            "Re-run the analysis after the underlying problem is fixed."
        )

    if ml.novelty_pattern in ("NOVELTY", "LEARNING"):
        return (
            "EXTEND: Wait for the effect trajectory to stabilise before deciding. "
            "A premature shipping decision risks acting on a transient signal."
        )

    if not stats.is_significant:
        if stats.overall_recommendation == "RUN":
            return (
                "DO_NOT_SHIP yet: the experiment has not reached its planned sample size. "
                "Continue running to accumulate sufficient power."
            )
        return (
            "DO_NOT_SHIP: the treatment did not show a statistically significant effect. "
            "Consider redesigning the experiment or increasing the effect size."
        )

    if ml.overall_verdict == "NEEDS_REVIEW":
        return (
            "SHIP with caution: the result is statistically significant, but data quality "
            "warnings were raised. Review the flagged issues before full rollout."
        )

    return (
        "SHIP: the result is statistically significant and the data is clean. "
        "The evidence supports rolling out the treatment."
    )


def _unknowns(stats: "FullAnalysisResult", ml: "MLAnalysisSummary") -> str:
    parts = ["Long-run effects beyond the experiment window remain unknown."]

    if not ml.hte_top_modifier and not ml.responsive_segments:
        parts.append(
            "Differential effects across user segments have not been measured."
        )
    elif ml.hte_top_modifier:
        parts.append(
            "Performance in user groups not captured by the top treatment modifier "
            "has not been characterised."
        )

    return " ".join(parts)
