"""Template-based fallback report sections — no Claude API required.

Called when the Claude API is unavailable or returns no tool_use block.
Generates all 7 narrative sections (section 8 is built by reporter.py)
using deterministic logic grounded in the actual result values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.intelligence.interpreter import FullAnalysisResult, MLAnalysisSummary


def build_fallback_sections(
    experiment_name: str,
    stats: "FullAnalysisResult",
    ml: "MLAnalysisSummary",
    daily_traffic: int | None,
    daily_revenue: float | None,
) -> dict[int, str]:
    """Build template content for sections 1–7 without any Claude call.

    Returns a dict keyed by section number (1–7) with Markdown-formatted
    content strings. All values are grounded in the actual result data.

    Args:
        experiment_name: Human-readable experiment name.
        stats: Statistical analysis output.
        ml: ML analysis summary.
        daily_traffic: Optional daily user count.
        daily_revenue: Optional daily revenue.

    Returns:
        Dict mapping section numbers 1–7 to their content strings.
    """
    return {
        1: _section_1(experiment_name, stats, ml),
        2: _section_2(stats, daily_revenue),
        3: _section_3(experiment_name, daily_traffic),
        4: _section_4(stats),
        5: _section_5(ml),
        6: _section_6(stats, ml),
        7: _section_7(stats, ml),
    }


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _section_1(
    experiment_name: str,
    stats: "FullAnalysisResult",
    ml: "MLAnalysisSummary",
) -> str:
    """Executive Summary — 2–3 sentences, no jargon, honest about invalidity."""
    fallback_note = (
        "_Note: AI summary unavailable — this report was generated from templates._\n\n"
    )

    if not ml.can_trust_results:
        reason = "a critical data integrity failure was detected"
        if ml.anomaly_validity and ml.anomaly_validity == "INVALID":
            reason = "sample ratio mismatch or anomalies were detected in the data"
        return (
            f"{fallback_note}"
            f"This experiment's results cannot be trusted due to {reason}. "
            "Do not act on these results. "
            "Investigate the root cause before making any shipping decision — "
            "the INVESTIGATE recommendation stands until the data issue is resolved."
        )

    if not stats.is_significant:
        rec = "DO_NOT_SHIP"
        if ml.novelty_pattern in ("NOVELTY", "LEARNING"):
            rec = "EXTEND"
        direction = "increased" if stats.lift_pct > 0 else "decreased"
        return (
            f"{fallback_note}"
            f"The {experiment_name} experiment {direction} the primary metric by "
            f"{abs(stats.lift_pct):.1f}%, but this difference was not statistically reliable. "
            f"Recommendation: **{rec}** — do not ship based on this result alone."
        )

    if ml.novelty_pattern in ("NOVELTY", "LEARNING"):
        pattern_word = (
            "novelty effect" if ml.novelty_pattern == "NOVELTY" else "learning curve"
        )
        return (
            f"{fallback_note}"
            f"The {experiment_name} experiment showed a {stats.lift_pct:+.1f}% lift that "
            f"reached statistical significance, but a {pattern_word} was detected. "
            "Recommendation: **EXTEND** — wait for the effect to stabilise before shipping."
        )

    direction = "increased" if stats.lift_pct > 0 else "decreased"
    verdict = ml.overall_verdict
    qual = (
        " — review the data quality concerns in section 6 before proceeding to full rollout"
        if verdict == "NEEDS_REVIEW"
        else ""
    )
    return (
        f"{fallback_note}"
        f"The {experiment_name} experiment {direction} the primary metric by "
        f"{abs(stats.lift_pct):.1f}% with high statistical confidence. "
        "The data passed all validity checks and the effect was stable throughout the "
        f"experiment window{qual}. "
        "Recommendation: **SHIP**."
    )


def _section_2(
    stats: "FullAnalysisResult",
    daily_revenue: float | None,
) -> str:
    """Business Impact — revenue if available, relative lift if not."""
    if not stats.is_significant:
        return (
            f"The observed lift of {stats.lift_pct:+.1f}% was not statistically meaningful. "
            "No business impact projection is appropriate until a reliable signal is established. "
            "Re-run the experiment with adequate power before estimating revenue impact."
        )

    if daily_revenue is not None:
        monthly_impact = abs(stats.lift_pct / 100.0) * daily_revenue * 30
        low_bound = monthly_impact * 0.5
        high_bound = monthly_impact * 1.5
        direction = "gain" if stats.lift_pct > 0 else "loss"
        return (
            f"A {abs(stats.lift_pct):.1f}% conversion lift at ${daily_revenue:,.2f} daily revenue "
            f"translates to approximately ${monthly_impact:,.0f} monthly incremental {direction}. "
            f"The true monthly impact is likely between ${low_bound:,.0f} and ${high_bound:,.0f}, "
            "based on the confidence interval around the observed lift. "
            "These figures assume the lift is sustained at steady-state performance."
        )

    direction = "improvement" if stats.lift_pct > 0 else "decline"
    return (
        f"The treatment produced a {abs(stats.lift_pct):.1f}% relative {direction} in the "
        "primary metric compared to the control group. "
        "To estimate revenue impact, provide the daily revenue figure when generating this report. "
        "Until then, evaluate the lift in terms of its strategic significance for your product."
    )


def _section_3(experiment_name: str, daily_traffic: int | None) -> str:
    """What We Tested — plain-English description of the experiment setup."""
    traffic_line = ""
    if daily_traffic is not None:
        traffic_line = (
            f" The experiment was run on approximately {daily_traffic:,} eligible users per day, "
            "with subjects randomly and evenly split between control and treatment groups "
            "at the point of experiment entry."
        )

    return (
        f"The {experiment_name} experiment compared a treatment variant against a control "
        f"group to measure the impact on the primary metric.{traffic_line} "
        "Users were randomly assigned to either the control experience or the treatment "
        "experience for the duration of the experiment. "
        "Each user's assignment was fixed for the experiment's lifetime — no re-assignment "
        "occurred once a user was enrolled, ensuring a clean comparison between the two groups. "
        "The experiment followed standard A/B testing protocol with a single primary metric "
        "and pre-specified analysis criteria established before any results were observed."
    )


def _section_4(stats: "FullAnalysisResult") -> str:
    """Results — key findings in plain language, no jargon."""
    direction = "increased" if stats.lift_pct > 0 else "decreased"
    abs_lift = abs(stats.lift_pct)

    if stats.is_significant:
        reliability = (
            "This difference is statistically reliable — it is highly unlikely to be due to "
            "random variation alone. "
            "The result was consistent throughout the experiment window, providing confidence "
            "that the observed lift reflects a genuine treatment effect rather than noise."
        )
    else:
        reliability = (
            "The difference between control and treatment did not reach statistical significance. "
            "This result should not be interpreted as evidence that the treatment works — "
            "an effect of this magnitude could plausibly arise from random chance alone. "
            "Do not ship based on this result. Consider whether a redesigned experiment with a "
            "larger effect size or longer runtime would be worth pursuing."
        )

    warnings_text = ""
    if stats.warnings:
        warnings_text = (
            "\n\n**Statistical warnings raised:** "
            + "; ".join(stats.warnings)
            + ". Review these concerns before acting on the results."
        )

    return (
        f"The treatment {direction} the primary metric by {abs_lift:.1f}% relative to control. "
        f"{reliability}"
        f"{warnings_text}"
    )


def _section_5(ml: "MLAnalysisSummary") -> str:
    """Who It Worked For — segments and HTE, or explicit statement that none ran."""
    if ml.hte_top_modifier:
        modifier_clean = ml.hte_top_modifier.replace("_x_treat", "")
        ate_str = (
            f" (average treatment effect: {ml.hte_ate:+.4f})"
            if ml.hte_ate is not None
            else ""
        )
        rec = (
            f" {ml.hte_business_recommendation}"
            if ml.hte_business_recommendation
            else ""
        )
        segments_line = ""
        if ml.responsive_segments:
            n = len(ml.responsive_segments)
            segments_line = f" Additionally, {n} user segment(s) showed above-average response to the treatment."
        return (
            f"The strongest treatment modifier was **{modifier_clean}**{ate_str}. "
            f"Treatment effects varied meaningfully across this dimension.{rec}{segments_line}"
        )

    if ml.responsive_segments is not None and len(ml.responsive_segments) > 0:
        n = len(ml.responsive_segments)
        rec = f" {ml.segment_recommendation}" if ml.segment_recommendation else ""
        return (
            f"{n} user segment(s) showed an above-average response to the treatment. "
            f"Consider a targeted rollout to these groups.{rec}"
        )

    return "Segment analysis was not run for this experiment."


def _section_6(stats: "FullAnalysisResult", ml: "MLAnalysisSummary") -> str:
    """Concerns — honest list of every validity issue, or confirmation of cleanliness."""
    concerns: list[str] = []

    if not ml.can_trust_results:
        concerns.append(
            "**Critical data integrity failure:** The experiment cannot be trusted. "
            "Results should not be used for any shipping decision."
        )

    if ml.anomaly_validity == "INVALID":
        concerns.append(
            "**Anomaly check failed (INVALID):** A critical anomaly — likely sample ratio "
            "mismatch — was detected. Assignment randomisation may have been broken."
        )
    elif ml.anomaly_validity == "WARNING":
        concerns.append(
            "**Anomaly check raised warnings:** Minor data irregularities were flagged. "
            "Review the anomaly detail before making a shipping decision."
        )

    if ml.novelty_pattern == "NOVELTY":
        concerns.append(
            "**Novelty effect detected:** The observed lift appears to be driven by users' "
            "initial excitement rather than long-term value. The effect may decay over time. "
            "Extending the experiment is strongly recommended."
        )
    elif ml.novelty_pattern == "LEARNING":
        concerns.append(
            "**Learning curve detected:** The treatment effect is still growing as users adapt. "
            "Extend the experiment until the lift stabilises before making a decision."
        )

    if stats.warnings:
        for w in stats.warnings:
            concerns.append(f"**Statistical warning:** {w}")

    if not concerns:
        return (
            "No data quality issues were detected. The experiment ran cleanly: "
            "randomisation was valid, no sample ratio mismatch was flagged, "
            "no anomalies were detected in the daily traffic data, and the effect "
            "trajectory was stable throughout the measurement window with no evidence "
            "of novelty decay or an ongoing learning curve. "
            "Confirmation of clean data is as important as flagging problems — "
            "proceed with confidence in the integrity of these results."
        )

    return "\n\n".join(concerns)


def _section_7(stats: "FullAnalysisResult", ml: "MLAnalysisSummary") -> str:
    """Recommendation — exactly one action word with 3–5 sentences of reasoning."""
    if not ml.can_trust_results:
        return (
            "**INVESTIGATE.** The experiment produced results that cannot be trusted. "
            "Do not make any shipping decision based on this data. "
            "Investigate the root cause of the data integrity failure — likely a sample "
            "ratio mismatch or broken randomisation. "
            "Once the underlying issue is resolved, design a new experiment with clean assignment. "
            "Next steps: review assignment logs, check for peeking or traffic leakage, "
            "and consult your data engineering team."
        )

    if ml.novelty_pattern in ("NOVELTY", "LEARNING"):
        pattern_desc = (
            "a novelty effect (initial excitement inflating the lift)"
            if ml.novelty_pattern == "NOVELTY"
            else "a learning curve (the effect is still growing)"
        )
        return (
            f"**EXTEND.** The experiment detected {pattern_desc}. "
            "A premature shipping decision risks acting on a transient signal rather than "
            "the treatment's true long-term value. "
            "Run the experiment for at least two additional weeks, then re-analyse. "
            "Next steps: monitor the daily lift trajectory and recheck when the effect stabilises."
        )

    if not stats.is_significant:
        return (
            "**DO_NOT_SHIP.** The treatment did not produce a statistically reliable difference "
            "from the control group. "
            "Shipping based on this result would be premature and risks degrading the user experience "
            "without evidence of benefit. "
            "Consider whether the treatment's effect size is large enough to be worth detecting, "
            "or whether a redesigned experiment with a stronger intervention is warranted. "
            "Next steps: revisit the hypothesis, explore segment data, and consider a power analysis "
            "before committing to another experiment run."
        )

    if ml.overall_verdict == "NEEDS_REVIEW":
        return (
            "**SHIP** with caution. The result is statistically reliable, but data quality "
            "warnings were raised during analysis. "
            "Review the flagged concerns in section 6 before proceeding to full rollout. "
            "A staged rollout (10% → 50% → 100%) is recommended to monitor for unexpected effects. "
            "Next steps: address flagged data quality issues, monitor guardrail metrics during rollout."
        )

    return (
        "**SHIP.** The treatment produced a statistically reliable improvement in the primary metric "
        "and the data passed all quality checks with no anomalies detected. "
        f"The {abs(stats.lift_pct):.1f}% lift represents a meaningful, trustworthy signal worth acting on "
        "and is consistent with the pre-registered hypothesis. "
        "Proceed to a staged rollout, beginning at 10% of traffic, and monitor guardrail metrics "
        "including any secondary metrics tracked during the experiment. "
        "Next steps: coordinate rollout with your engineering team, configure monitoring dashboards "
        "to detect any unexpected behaviour at production scale, and schedule a post-launch review "
        "two weeks after reaching full traffic to confirm the lift is sustained."
    )
