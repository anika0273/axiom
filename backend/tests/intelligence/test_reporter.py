"""Tests for backend/app/intelligence/reporter.py.

All Claude API calls are mocked — the real API is never hit.
Tests cover:
  - Report contains all 8 sections
  - Section 8 is programmatic (contains actual p-value)
  - Sections 1–7 contain no p-values after mocked output with clean text
  - SHIP only when significant + valid + no novelty
  - DO_NOT_SHIP when not significant + adequately powered
  - EXTEND when novelty detected
  - INVESTIGATE when INVALID
  - Grounding validator overrides SHIP on non-significant result to EXTEND
  - Grounding validator overrides SHIP when can_trust_results=False to INVESTIGATE
  - Grounding validator overrides SHIP when novelty detected to EXTEND
  - Fallback generates valid report with no Claude API
  - word_count is between 400 and 800
  - build_fallback_report: all 8 sections present, section 8 programmatic
"""

from __future__ import annotations

import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.intelligence.interpreter import FullAnalysisResult, MLAnalysisSummary
from app.intelligence.reporter import (
    ReportSection,
    StakeholderReport,
    _validate_grounding,
    build_fallback_report,
    generate_report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sig_stats() -> FullAnalysisResult:
    """Significant, clean result with positive lift."""
    return FullAnalysisResult(
        is_significant=True,
        p_value=0.0003,
        lift_pct=18.4,
        lift_abs=0.0184,
        overall_recommendation="STOP_WIN",
        warnings=[],
        plain_english="Treatment significantly improved conversion.",
    )


def _nonsig_stats() -> FullAnalysisResult:
    """Non-significant result."""
    return FullAnalysisResult(
        is_significant=False,
        p_value=0.38,
        lift_pct=2.1,
        lift_abs=0.002,
        overall_recommendation="RUN",
        warnings=[],
        plain_english="No significant effect detected.",
    )


def _clean_ml() -> MLAnalysisSummary:
    """Clean ML result — all checks passed, stable novelty."""
    return MLAnalysisSummary(
        overall_verdict="CLEAN",
        can_trust_results=True,
        key_insights=["Data quality checks passed."],
        recommendation="Proceed with shipping decision.",
        anomaly_validity="VALID",
        novelty_pattern="STABLE",
    )


def _invalid_ml() -> MLAnalysisSummary:
    """INVALID ML result — SRM detected, cannot trust results."""
    return MLAnalysisSummary(
        overall_verdict="INVALID",
        can_trust_results=False,
        key_insights=["SRM detected: assignment ratio 60/40 vs expected 50/50."],
        recommendation="Do not act on these results.",
        anomaly_validity="INVALID",
        novelty_pattern=None,
    )


def _novelty_ml() -> MLAnalysisSummary:
    """NEEDS_REVIEW ML result — novelty effect detected."""
    return MLAnalysisSummary(
        overall_verdict="NEEDS_REVIEW",
        can_trust_results=True,
        key_insights=["Novelty effect detected. Lift is decaying."],
        recommendation="Extend experiment to observe steady-state.",
        anomaly_validity="VALID",
        novelty_pattern="NOVELTY",
    )


def _make_tool_output(
    recommendation: str = "SHIP",
    confidence_level: str = "High",
    include_pvalue: bool = False,
) -> dict[str, Any]:
    """Build a realistic mock tool_use response from Claude (~450 words in sections 1-7)."""
    extra = " The p-value was 0.0003." if include_pvalue else ""
    section_4_content = (
        "The treatment increased the primary metric by 18.4% relative to the control group. "
        "This result is statistically reliable — the observed difference is highly unlikely to be "
        f"due to random variation alone.{extra} "
        "The magnitude of the improvement is meaningful and consistent across the full experiment "
        "window, with no sign of the effect diminishing toward the end of the run. "
        "The 18.4% relative lift translates to a substantial absolute improvement in conversion "
        "that was sustained throughout the measurement period."
    )
    return {
        "section_1": (
            "The checkout redesign experiment increased conversion by 18.4% compared to the control "
            "group, a result we can rely on with high statistical confidence. "
            "This improvement was stable throughout the 21-day experiment window and shows no sign "
            "of being a transient novelty effect. "
            "Based on this strong, clean positive signal, the recommendation is to SHIP the "
            "treatment to all users."
        ),
        "section_2": (
            "A conversion lift of 18.4% represents a meaningful improvement in purchase rate "
            "that will translate directly to incremental revenue. "
            "The true lift lies comfortably within a range that supports a confident shipping "
            "decision — even at the lower bound of the confidence interval, the impact remains "
            "commercially significant. "
            "Teams should monitor checkout revenue carefully during rollout to confirm that the "
            "experiment-measured lift materialises at production scale. "
            "Any revenue attribution model should account for the 21-day experiment window used "
            "to produce these estimates."
        ),
        "section_3": (
            "The experiment tested a redesigned checkout button — orange instead of the existing "
            "green — to determine whether the visual change would improve purchase conversion rate. "
            "Users visiting the checkout page were randomly and evenly split between the control "
            "group (green button) and the treatment group (orange button). "
            "The experiment ran for 21 consecutive days, accumulating over ten thousand user "
            "observations across both groups, which was sufficient to detect the pre-specified "
            "minimum detectable effect with high reliability. "
            "Assignment was sticky — each user saw the same button colour on every return visit "
            "during the experiment period."
        ),
        "section_4": section_4_content,
        "section_5": (
            "Segment analysis was not run for this experiment. "
            "The primary analysis covered the full user population without stratification. "
            "Future experiments may wish to segment by device type or user tenure to understand "
            "whether the button colour effect is uniform across different user groups."
        ),
        "section_6": (
            "No data quality issues were detected. The experiment ran cleanly: randomisation "
            "was valid, no sample ratio mismatch was detected, no anomalies were flagged in the "
            "daily traffic data, and the effect trajectory was stable throughout the experiment "
            "window with no signs of novelty decay or ongoing learning effects. "
            "These clean signals increase confidence in the reported lift estimate."
        ),
        "section_7": (
            f"{recommendation}. The treatment produced a statistically reliable 18.4% improvement "
            "in conversion with clean data and no validity concerns of any kind. "
            "This represents a strong positive signal across the full experiment run with no "
            "evidence of data integrity issues that would call the result into question. "
            "Proceed to a staged rollout starting at 10% of traffic, monitoring guardrail metrics "
            "including average order value and return rate throughout. "
            "Schedule a post-launch review two weeks after reaching full traffic to confirm "
            "that the measured lift is sustained in production."
        ),
        "recommendation": recommendation,
        "confidence_level": confidence_level,
        "confidence_reasoning": (
            "The result is statistically significant, the data passed all quality checks, "
            "and the effect trajectory was stable throughout the experiment."
        ),
        "key_metric": "+18.4% conversion lift (significant)",
    }


def _mock_claude_response(tool_output: dict[str, Any]) -> MagicMock:
    """Build a mock anthropic response that returns the given tool output."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = tool_output

    usage = MagicMock()
    usage.input_tokens = 1200
    usage.output_tokens = 850

    response = MagicMock()
    response.content = [tool_block]
    response.usage = usage
    return response


# ---------------------------------------------------------------------------
# Core structure tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_report_contains_all_8_sections():
    """Generated report must have exactly 8 sections numbered 1–8."""
    mock_resp = _mock_claude_response(_make_tool_output())
    client_mock = MagicMock()
    client_mock.messages.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.intelligence.reporter.anthropic.AsyncAnthropic", return_value=client_mock
    ):
        report = await generate_report(
            experiment_name="Test Experiment",
            stats_result=_sig_stats(),
            ml_result=_clean_ml(),
        )

    assert len(report.sections) == 8
    for i, section in enumerate(report.sections, start=1):
        assert section.section_number == i


@pytest.mark.asyncio
async def test_section_8_is_programmatic():
    """Section 8 must be programmatic and contain the actual p-value."""
    stats = _sig_stats()
    mock_resp = _mock_claude_response(_make_tool_output())
    client_mock = MagicMock()
    client_mock.messages.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.intelligence.reporter.anthropic.AsyncAnthropic", return_value=client_mock
    ):
        report = await generate_report(
            experiment_name="Test Experiment",
            stats_result=stats,
            ml_result=_clean_ml(),
        )

    section_8 = report.sections[7]
    assert section_8.section_number == 8
    assert not section_8.is_ai_generated
    # Section 8 must contain the actual p-value from stats_result
    assert str(stats.p_value)[:6] in section_8.content


@pytest.mark.asyncio
async def test_sections_1_to_7_are_ai_generated():
    """Sections 1–7 must be marked as AI-generated."""
    mock_resp = _mock_claude_response(_make_tool_output())
    client_mock = MagicMock()
    client_mock.messages.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.intelligence.reporter.anthropic.AsyncAnthropic", return_value=client_mock
    ):
        report = await generate_report(
            experiment_name="Test Experiment",
            stats_result=_sig_stats(),
            ml_result=_clean_ml(),
        )

    for section in report.sections[:7]:
        assert (
            section.is_ai_generated
        ), f"Section {section.section_number} should be AI-generated"


@pytest.mark.asyncio
async def test_sections_1_to_7_contain_no_pvalues():
    """Sections 1–7 must not contain p-values in the mocked output (clean mock)."""
    mock_resp = _mock_claude_response(_make_tool_output(include_pvalue=False))
    client_mock = MagicMock()
    client_mock.messages.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.intelligence.reporter.anthropic.AsyncAnthropic", return_value=client_mock
    ):
        report = await generate_report(
            experiment_name="Test Experiment",
            stats_result=_sig_stats(),
            ml_result=_clean_ml(),
        )

    pvalue_pattern = re.compile(r"\bp[\s]*[=<>]+\s*0\.\d+|\bp-value\b", re.IGNORECASE)
    for section in report.sections[:7]:
        assert not pvalue_pattern.search(
            section.content
        ), f"Section {section.section_number} contains p-value jargon: {section.content[:200]}"


# ---------------------------------------------------------------------------
# Recommendation logic tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ship_recommendation_when_significant_valid_stable():
    """SHIP when is_significant=True, can_trust_results=True, no novelty."""
    mock_resp = _mock_claude_response(_make_tool_output(recommendation="SHIP"))
    client_mock = MagicMock()
    client_mock.messages.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.intelligence.reporter.anthropic.AsyncAnthropic", return_value=client_mock
    ):
        report = await generate_report(
            experiment_name="Checkout Redesign",
            stats_result=_sig_stats(),
            ml_result=_clean_ml(),
        )

    assert report.recommendation == "SHIP"


@pytest.mark.asyncio
async def test_do_not_ship_when_not_significant():
    """DO_NOT_SHIP when result is not significant and clean ML."""
    tool_out = _make_tool_output(recommendation="DO_NOT_SHIP", confidence_level="Low")
    tool_out["section_1"] = (
        "The test did not show a statistically reliable effect. "
        "The observed lift of 2.1% is within the range of random variation. "
        "Recommendation: DO_NOT_SHIP."
    )
    tool_out["key_metric"] = "No significant effect (lift: +2.1%)"
    mock_resp = _mock_claude_response(tool_out)
    client_mock = MagicMock()
    client_mock.messages.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.intelligence.reporter.anthropic.AsyncAnthropic", return_value=client_mock
    ):
        report = await generate_report(
            experiment_name="Button Color Test",
            stats_result=_nonsig_stats(),
            ml_result=_clean_ml(),
        )

    assert report.recommendation == "DO_NOT_SHIP"


@pytest.mark.asyncio
async def test_extend_when_novelty_detected():
    """EXTEND when novelty_pattern=NOVELTY, even if result is significant."""
    sig_stats = _sig_stats()
    tool_out = _make_tool_output(recommendation="EXTEND", confidence_level="Medium")
    tool_out["section_6"] = (
        "A novelty effect was detected. The lift appears to be driven by users' initial "
        "excitement with the new design. This effect may decay as users habituate to the treatment."
    )
    tool_out["key_metric"] = "+18.4% lift (novelty effect detected — extend)"
    mock_resp = _mock_claude_response(tool_out)
    client_mock = MagicMock()
    client_mock.messages.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.intelligence.reporter.anthropic.AsyncAnthropic", return_value=client_mock
    ):
        report = await generate_report(
            experiment_name="Checkout Redesign",
            stats_result=sig_stats,
            ml_result=_novelty_ml(),
        )

    assert report.recommendation == "EXTEND"


@pytest.mark.asyncio
async def test_investigate_when_invalid():
    """INVESTIGATE when can_trust_results=False."""
    tool_out = _make_tool_output(recommendation="INVESTIGATE", confidence_level="Low")
    tool_out["section_1"] = (
        "This experiment's results cannot be trusted due to a sample ratio mismatch. "
        "Do not act on these results. Recommendation: INVESTIGATE."
    )
    tool_out["key_metric"] = "Results invalid — do not act"
    mock_resp = _mock_claude_response(tool_out)
    client_mock = MagicMock()
    client_mock.messages.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.intelligence.reporter.anthropic.AsyncAnthropic", return_value=client_mock
    ):
        report = await generate_report(
            experiment_name="Checkout Redesign",
            stats_result=_sig_stats(),
            ml_result=_invalid_ml(),
        )

    assert report.recommendation == "INVESTIGATE"


# ---------------------------------------------------------------------------
# Grounding validator tests
# ---------------------------------------------------------------------------


def test_grounding_validator_overrides_ship_on_nonsig():
    """Validator must override SHIP to EXTEND when is_significant=False."""
    tool_out = _make_tool_output(recommendation="SHIP")
    fixed = _validate_grounding(
        tool_out, _nonsig_stats(), _clean_ml(), daily_revenue=None
    )
    assert fixed["recommendation"] == "EXTEND"


def test_grounding_validator_overrides_ship_when_invalid():
    """Validator must override SHIP to INVESTIGATE when can_trust_results=False."""
    tool_out = _make_tool_output(recommendation="SHIP")
    fixed = _validate_grounding(
        tool_out, _sig_stats(), _invalid_ml(), daily_revenue=None
    )
    assert fixed["recommendation"] == "INVESTIGATE"


def test_grounding_validator_overrides_ship_when_novelty():
    """Validator must override SHIP to EXTEND when novelty_pattern=NOVELTY."""
    tool_out = _make_tool_output(recommendation="SHIP")
    fixed = _validate_grounding(
        tool_out, _sig_stats(), _novelty_ml(), daily_revenue=None
    )
    assert fixed["recommendation"] == "EXTEND"


def test_grounding_validator_preserves_valid_ship():
    """Validator must not modify a valid SHIP recommendation."""
    tool_out = _make_tool_output(recommendation="SHIP")
    fixed = _validate_grounding(tool_out, _sig_stats(), _clean_ml(), daily_revenue=None)
    assert fixed["recommendation"] == "SHIP"


def test_grounding_validator_fills_empty_key_metric():
    """Validator must substitute key_metric when it is empty."""
    tool_out = _make_tool_output(recommendation="SHIP")
    tool_out["key_metric"] = ""
    fixed = _validate_grounding(tool_out, _sig_stats(), _clean_ml(), daily_revenue=None)
    assert fixed["key_metric"] != ""
    assert "18.4" in fixed["key_metric"] or "lift" in fixed["key_metric"].lower()


def test_grounding_validator_precedence_invalid_beats_novelty():
    """INVESTIGATE takes priority over EXTEND when both conditions apply."""
    novelty_and_invalid = MLAnalysisSummary(
        overall_verdict="INVALID",
        can_trust_results=False,
        key_insights=[],
        recommendation="Investigate.",
        anomaly_validity="INVALID",
        novelty_pattern="NOVELTY",
    )
    tool_out = _make_tool_output(recommendation="SHIP")
    fixed = _validate_grounding(
        tool_out, _sig_stats(), novelty_and_invalid, daily_revenue=None
    )
    # can_trust_results=False is checked first, so INVESTIGATE wins
    assert fixed["recommendation"] == "INVESTIGATE"


# ---------------------------------------------------------------------------
# Fallback report tests
# ---------------------------------------------------------------------------


def test_fallback_generates_valid_report_no_claude():
    """build_fallback_report must produce a complete report without any API call."""
    report = build_fallback_report(
        experiment_name="Fallback Test",
        stats_result=_sig_stats(),
        ml_result=_clean_ml(),
    )

    assert isinstance(report, StakeholderReport)
    assert len(report.sections) == 8
    assert report.recommendation in ("SHIP", "DO_NOT_SHIP", "EXTEND", "INVESTIGATE")
    assert report.markdown_content != ""
    assert report.html_content != ""
    assert "fallback" in report.prompt_version


def test_fallback_section_8_programmatic():
    """Fallback section 8 must be programmatic and contain the p-value."""
    stats = _sig_stats()
    report = build_fallback_report(
        experiment_name="Fallback Test",
        stats_result=stats,
        ml_result=_clean_ml(),
    )
    section_8 = report.sections[7]
    assert not section_8.is_ai_generated
    assert str(stats.p_value)[:6] in section_8.content


def test_fallback_all_sections_programmatic():
    """All sections in fallback report must be marked as not AI-generated."""
    report = build_fallback_report(
        experiment_name="Fallback Test",
        stats_result=_sig_stats(),
        ml_result=_clean_ml(),
    )
    for section in report.sections:
        assert not section.is_ai_generated


def test_fallback_ship_when_significant_clean():
    """Fallback recommends SHIP for significant, clean results."""
    report = build_fallback_report(
        experiment_name="Fallback Test",
        stats_result=_sig_stats(),
        ml_result=_clean_ml(),
    )
    assert report.recommendation == "SHIP"


def test_fallback_do_not_ship_when_not_significant():
    """Fallback recommends DO_NOT_SHIP for non-significant, clean results."""
    report = build_fallback_report(
        experiment_name="Fallback Test",
        stats_result=_nonsig_stats(),
        ml_result=_clean_ml(),
    )
    assert report.recommendation == "DO_NOT_SHIP"


def test_fallback_extend_when_novelty():
    """Fallback recommends EXTEND when novelty effect is detected."""
    report = build_fallback_report(
        experiment_name="Fallback Test",
        stats_result=_sig_stats(),
        ml_result=_novelty_ml(),
    )
    assert report.recommendation == "EXTEND"


def test_fallback_investigate_when_invalid():
    """Fallback recommends INVESTIGATE when can_trust_results=False."""
    report = build_fallback_report(
        experiment_name="Fallback Test",
        stats_result=_sig_stats(),
        ml_result=_invalid_ml(),
    )
    assert report.recommendation == "INVESTIGATE"


# ---------------------------------------------------------------------------
# Word count tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_word_count_between_400_and_800():
    """AI-generated report word count (sections 1–7) must be 400–800 words."""
    mock_resp = _mock_claude_response(_make_tool_output())
    client_mock = MagicMock()
    client_mock.messages.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.intelligence.reporter.anthropic.AsyncAnthropic", return_value=client_mock
    ):
        report = await generate_report(
            experiment_name="Word Count Test",
            stats_result=_sig_stats(),
            ml_result=_clean_ml(),
        )

    assert (
        400 <= report.word_count <= 800
    ), f"word_count={report.word_count} is outside the 400–800 target range"


def test_fallback_word_count_between_400_and_800():
    """Fallback report word count (sections 1–7) must be 400–800 words."""
    report = build_fallback_report(
        experiment_name="Word Count Test",
        stats_result=_sig_stats(),
        ml_result=_clean_ml(),
        daily_revenue=10000.0,
    )
    assert (
        400 <= report.word_count <= 800
    ), f"fallback word_count={report.word_count} is outside the 400–800 target range"


# ---------------------------------------------------------------------------
# Report metadata tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_report_metadata_fields():
    """Report must have populated title, generated_at, prompt_version, key_metric."""
    mock_resp = _mock_claude_response(_make_tool_output())
    client_mock = MagicMock()
    client_mock.messages.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.intelligence.reporter.anthropic.AsyncAnthropic", return_value=client_mock
    ):
        report = await generate_report(
            experiment_name="Metadata Test",
            stats_result=_sig_stats(),
            ml_result=_clean_ml(),
        )

    assert "Metadata Test" in report.title
    assert report.generated_at is not None
    assert report.prompt_version == "reporter_v1"
    assert report.key_metric != ""
    assert report.confidence_level in ("High", "Medium", "Low")
    assert report.confidence_reasoning != ""


@pytest.mark.asyncio
async def test_ai_and_programmatic_section_lists():
    """ai_generated_sections and programmatic_sections must be correctly populated."""
    mock_resp = _mock_claude_response(_make_tool_output())
    client_mock = MagicMock()
    client_mock.messages.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.intelligence.reporter.anthropic.AsyncAnthropic", return_value=client_mock
    ):
        report = await generate_report(
            experiment_name="Section List Test",
            stats_result=_sig_stats(),
            ml_result=_clean_ml(),
        )

    assert len(report.ai_generated_sections) == 7
    assert len(report.programmatic_sections) == 1
    assert "Technical Appendix" in report.programmatic_sections


@pytest.mark.asyncio
async def test_fallback_triggered_on_api_error():
    """API error must trigger fallback report, not an exception."""
    import anthropic as anthropic_module

    client_mock = MagicMock()
    client_mock.messages.create = AsyncMock(
        side_effect=anthropic_module.APITimeoutError(request=MagicMock())
    )

    with patch(
        "app.intelligence.reporter.anthropic.AsyncAnthropic", return_value=client_mock
    ):
        report = await generate_report(
            experiment_name="Error Test",
            stats_result=_sig_stats(),
            ml_result=_clean_ml(),
        )

    assert isinstance(report, StakeholderReport)
    assert "fallback" in report.prompt_version
    assert len(report.sections) == 8


@pytest.mark.asyncio
async def test_markdown_and_html_content_populated():
    """Both markdown_content and html_content must be non-empty strings."""
    mock_resp = _mock_claude_response(_make_tool_output())
    client_mock = MagicMock()
    client_mock.messages.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.intelligence.reporter.anthropic.AsyncAnthropic", return_value=client_mock
    ):
        report = await generate_report(
            experiment_name="Content Test",
            stats_result=_sig_stats(),
            ml_result=_clean_ml(),
        )

    assert len(report.markdown_content) > 500
    assert len(report.html_content) > 500
    assert "<!DOCTYPE html>" in report.html_content
    assert "# Experiment Report" in report.markdown_content


@pytest.mark.asyncio
async def test_daily_revenue_reflected_in_report():
    """When daily_revenue is provided, key_metric or sections reference it."""
    sig = _sig_stats()
    tool_out = _make_tool_output()
    tool_out["section_2"] = (
        "A 18.4% conversion lift at $5,000.00 daily revenue equals approximately "
        "$27,600 monthly incremental gain. "
        "The true monthly impact is likely between $13,800 and $41,400, "
        "based on the confidence interval around the observed lift."
    )
    mock_resp = _mock_claude_response(tool_out)
    client_mock = MagicMock()
    client_mock.messages.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.intelligence.reporter.anthropic.AsyncAnthropic", return_value=client_mock
    ):
        report = await generate_report(
            experiment_name="Revenue Test",
            stats_result=sig,
            ml_result=_clean_ml(),
            daily_revenue=5000.0,
        )

    section_2 = report.sections[1]
    assert "$" in section_2.content or "revenue" in section_2.content.lower()
