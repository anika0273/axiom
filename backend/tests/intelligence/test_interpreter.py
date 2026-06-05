"""Tests for backend/app/intelligence/interpreter.py.

All Claude API calls are mocked — the real API is never hit in this suite.
Tests cover:
  - Streaming: chunks are yielded, assembled text is non-empty
  - Significant result: assembled text contains "significant"
  - Non-significant result: assembled text does NOT recommend SHIP
  - INVALID experiment: assembled text leads with the validity issue
  - build_fallback_interpretation: valid output for all result combinations
  - interpret_subgroup: returns a non-empty string
  - parse_stats_from_json / parse_ml_from_json: correctly hydrate from both JSON layouts
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.intelligence.interpreter import (
    FullAnalysisResult,
    MLAnalysisSummary,
    build_fallback_interpretation,
    interpret_results,
    interpret_subgroup,
    parse_ml_from_json,
    parse_stats_from_json,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sig_stats() -> FullAnalysisResult:
    """Significant, clean result with positive lift."""
    return FullAnalysisResult(
        is_significant=True,
        p_value=0.0003,
        lift_pct=31.4,
        lift_abs=0.0344,
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
        lift_abs=0.006,
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
        key_insights=["Novelty effect detected. Effect is decaying."],
        recommendation="Results need review.",
        anomaly_validity="VALID",
        novelty_pattern="NOVELTY",
    )


def _hte_ml() -> MLAnalysisSummary:
    """CLEAN ML result with HTE and segment data."""
    return MLAnalysisSummary(
        overall_verdict="CLEAN",
        can_trust_results=True,
        key_insights=["company_size is the top modifier."],
        recommendation="Proceed.",
        anomaly_validity="VALID",
        novelty_pattern="STABLE",
        hte_top_modifier="company_size_x_treat",
        hte_ate=0.0344,
        hte_business_recommendation="Target top 20% by predicted lift.",
        responsive_segments=[1, 4],
        segment_recommendation="Roll out to segments 1, 4.",
    )


# ---------------------------------------------------------------------------
# Stream mock helper
# ---------------------------------------------------------------------------


class _MockStream:
    """Async context manager that yields predefined text chunks."""

    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks

    @property
    def text_stream(self):
        async def _gen():
            for chunk in self._chunks:
                yield chunk

        return _gen()

    async def get_final_message(self) -> MagicMock:
        msg = MagicMock()
        msg.usage.input_tokens = 300
        msg.usage.output_tokens = 150
        return msg

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _patch_stream(chunks: list[str]):
    """Return a context manager that patches the anthropic client with a mock stream."""
    mock_stream = _MockStream(chunks)

    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream

    return patch(
        "app.intelligence.interpreter.anthropic.AsyncAnthropic",
        return_value=mock_client,
    )


def _patch_messages_create(text: str):
    """Patch client.messages.create for non-streaming calls."""
    content_block = MagicMock()
    content_block.text = text

    response = MagicMock()
    response.content = [content_block]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=response)

    return patch(
        "app.intelligence.interpreter.anthropic.AsyncAnthropic",
        return_value=mock_client,
    )


# ---------------------------------------------------------------------------
# Streaming tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_interpret_results_yields_chunks():
    """interpret_results should yield at least one chunk."""
    chunks = ["The ", "treatment ", "increased ", "conversion ", "by 31.4%."]
    with _patch_stream(chunks):
        received = []
        async for chunk in interpret_results(
            _sig_stats(), _clean_ml(), "Test Experiment"
        ):
            received.append(chunk)

    assert received == chunks
    assert "".join(received) != ""


@pytest.mark.asyncio
async def test_interpret_results_assembled_nonempty():
    """Assembled text from significant result must be non-empty."""
    chunks = ["Statistically ", "significant ", "result."]
    with _patch_stream(chunks):
        assembled = []
        async for chunk in interpret_results(_sig_stats(), _clean_ml(), "SaaS Trial"):
            assembled.append(chunk)

    assert len("".join(assembled)) > 0


@pytest.mark.asyncio
async def test_significant_result_contains_significant():
    """Assembled text for a significant result must contain the word 'significant'."""
    chunks = [
        "The SaaS trial ",
        "increased conversion by 31.4% — ",
        "a statistically significant result (p=0.0003).",
    ]
    with _patch_stream(chunks):
        assembled = []
        async for chunk in interpret_results(_sig_stats(), _clean_ml(), "SaaS Trial"):
            assembled.append(chunk)

    text = "".join(assembled).lower()
    assert "significant" in text


@pytest.mark.asyncio
async def test_nonsig_result_does_not_recommend_ship():
    """Assembled text for a non-significant result must not recommend SHIP as action."""
    chunks = [
        "The treatment did not show a statistically significant effect ",
        "(lift: +2.1%, p=0.38). ",
        "DO_NOT_SHIP: insufficient evidence to justify rollout.",
    ]
    with _patch_stream(chunks):
        assembled = []
        async for chunk in interpret_results(
            _nonsig_stats(), _clean_ml(), "Button Color Test"
        ):
            assembled.append(chunk)

    text = "".join(assembled)
    # Must not recommend bare SHIP as the action (DO_NOT_SHIP is fine)
    assert (
        "DO_NOT_SHIP" in text or "do not" in text.lower() or "ship" not in text.lower()
    )
    # Crucially: bare "SHIP" (as an action recommendation) should not appear
    import re

    # "SHIP" that is NOT preceded by "DO_NOT_" or "not "
    bare_ship = re.search(r"(?<![_\w])SHIP(?![\w])", text)
    do_not_ship = "DO_NOT_SHIP" in text or "do_not_ship" in text.lower()
    assert bare_ship is None or do_not_ship


@pytest.mark.asyncio
async def test_invalid_experiment_mentions_validity():
    """Assembled text for an INVALID experiment must mention the validity issue."""
    chunks = [
        "The results cannot be trusted due to critical data integrity issues. ",
        "INVESTIGATE: a sample ratio mismatch (SRM) was detected.",
    ]
    with _patch_stream(chunks):
        assembled = []
        async for chunk in interpret_results(
            _sig_stats(), _invalid_ml(), "Checkout Test"
        ):
            assembled.append(chunk)

    text = "".join(assembled).lower()
    # Must mention the integrity issue — any of these phrases is acceptable
    validity_mentioned = any(
        phrase in text
        for phrase in [
            "cannot be trusted",
            "data integrity",
            "invalid",
            "investigate",
            "srm",
            "sample ratio",
        ]
    )
    assert validity_mentioned


@pytest.mark.asyncio
async def test_novelty_result_recommends_extend():
    """A NOVELTY ML result should produce an EXTEND recommendation."""
    chunks = [
        "The treatment increased conversion by 31.4% — a statistically significant result. ",
        "However, a novelty effect was detected. ",
        "EXTEND: wait for steady-state before deciding.",
    ]
    with _patch_stream(chunks):
        assembled = []
        async for chunk in interpret_results(
            _sig_stats(), _novelty_ml(), "Homepage Redesign"
        ):
            assembled.append(chunk)

    text = "".join(assembled).lower()
    assert "extend" in text or "novelty" in text


# ---------------------------------------------------------------------------
# Fallback tests
# ---------------------------------------------------------------------------


def test_fallback_significant_clean():
    """Fallback for a significant + clean result should include SHIP."""
    result = build_fallback_interpretation(_sig_stats(), _clean_ml())
    assert isinstance(result, str)
    assert len(result) > 50
    assert "31.4" in result or "increased" in result
    assert "SHIP" in result


def test_fallback_nonsig_invalid():
    """Fallback for non-significant + INVALID should recommend INVESTIGATE."""
    result = build_fallback_interpretation(_nonsig_stats(), _invalid_ml())
    assert isinstance(result, str)
    assert "INVESTIGATE" in result
    assert "cannot be trusted" in result.lower() or "integrity" in result.lower()


def test_fallback_sig_needs_review():
    """Fallback for significant + NEEDS_REVIEW should be cautious but still ship."""
    needs_review = MLAnalysisSummary(
        overall_verdict="NEEDS_REVIEW",
        can_trust_results=True,
        key_insights=[],
        recommendation="Check flagged issues.",
        anomaly_validity="WARNING",
        novelty_pattern="STABLE",
    )
    result = build_fallback_interpretation(_sig_stats(), needs_review)
    assert isinstance(result, str)
    assert len(result) > 50
    # Should mention caution but ultimately ship
    assert "SHIP" in result or "ship" in result.lower()


def test_fallback_novelty():
    """Fallback for novelty effect should recommend EXTEND."""
    result = build_fallback_interpretation(_sig_stats(), _novelty_ml())
    assert "EXTEND" in result
    assert "novelty" in result.lower()


def test_fallback_no_segment_data():
    """Fallback with no ML analysis should include the segment-not-run sentence."""
    no_ml = MLAnalysisSummary(
        overall_verdict="NEEDS_REVIEW",
        can_trust_results=True,
        key_insights=[],
        recommendation="Insufficient data.",
        anomaly_validity=None,
        novelty_pattern=None,
    )
    result = build_fallback_interpretation(_sig_stats(), no_ml)
    assert "Segment analysis was not run" in result


# ---------------------------------------------------------------------------
# Subgroup interpretation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_interpret_subgroup_returns_nonempty():
    """interpret_subgroup should return a non-empty string."""
    segment_profile = {
        "id": 1,
        "size_pct": 0.32,
        "lift": 0.076,
        "significant": True,
        "description": "Enterprise accounts (50+ seats)",
    }
    with _patch_messages_create(
        "Segment 1 (32% of users) showed a significant lift of 0.0760 — "
        "driven by enterprise accounts with 50+ seats. "
        "Target this group for an accelerated rollout."
    ):
        result = await interpret_subgroup(segment_profile, "SaaS Trial")

    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_interpret_subgroup_fallback_on_error():
    """interpret_subgroup should return a fallback string when the API fails."""
    segment_profile = {
        "id": 2,
        "size_pct": 0.15,
        "lift": -0.012,
        "significant": False,
        "description": "Small teams (<5 seats)",
    }
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=Exception("API unavailable"))

    with patch(
        "app.intelligence.interpreter.anthropic.AsyncAnthropic",
        return_value=mock_client,
    ):
        result = await interpret_subgroup(segment_profile, "SaaS Trial")

    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# JSON hydration tests
# ---------------------------------------------------------------------------


def test_parse_stats_from_json_nested():
    """parse_stats_from_json handles the nested format (sample experiment JSON)."""
    json_data: dict[str, Any] = {
        "stats_result": {
            "primary_result": {
                "is_significant": True,
                "p_value": 0.000257,
                "lift_pct": 31.3869,
                "lift_abs": 0.0344,
                "test_statistic": 3.655,
                "test_type": "z-test",
                "sample_warnings": [],
                "interpretation": "Significant.",
            },
            "overall_recommendation": "STOP_WIN",
            "plain_english": "Winner.",
            "warnings": [],
        },
        "ml_result": {},
    }
    result = parse_stats_from_json(json_data)
    assert result.is_significant is True
    assert abs(result.p_value - 0.000257) < 1e-8
    assert abs(result.lift_pct - 31.3869) < 1e-4
    assert result.overall_recommendation == "STOP_WIN"


def test_parse_stats_from_json_empty_graceful():
    """parse_stats_from_json falls back to defaults when data is missing."""
    result = parse_stats_from_json({})
    assert result.is_significant is False
    assert result.p_value == 1.0
    assert result.lift_pct == 0.0
    assert result.overall_recommendation == "RUN"


def test_parse_ml_from_json_nested():
    """parse_ml_from_json handles the nested format correctly."""
    json_data: dict[str, Any] = {
        "ml_result": {
            "overall_verdict": "CLEAN",
            "can_trust_results": True,
            "key_insights": ["All checks passed."],
            "recommendation": "Proceed.",
            "anomaly": {"overall_validity": "VALID", "can_trust_results": True},
            "novelty": {"pattern": "STABLE"},
            "hte": {
                "ate": 0.0344,
                "top_interactions": ["company_size_x_treat"],
                "business_recommendation": "Target enterprises.",
            },
            "segments": {
                "responsive_segments": [1, 4],
                "overall_recommendation": "Roll out to segments 1, 4.",
            },
        }
    }
    result = parse_ml_from_json(json_data)
    assert result.overall_verdict == "CLEAN"
    assert result.can_trust_results is True
    assert result.anomaly_validity == "VALID"
    assert result.novelty_pattern == "STABLE"
    assert result.hte_top_modifier == "company_size_x_treat"
    assert abs(result.hte_ate - 0.0344) < 1e-6
    assert result.responsive_segments == [1, 4]


def test_parse_ml_from_json_flat_legacy():
    """parse_ml_from_json handles the flat (legacy) format from result_repo."""
    json_data: dict[str, Any] = {
        "overall_verdict": "NEEDS_REVIEW",
        "can_trust_results": True,
        "key_insights": [],
        "recommendation": "Review needed.",
        "capability_report": [],
    }
    result = parse_ml_from_json(json_data)
    assert result.overall_verdict == "NEEDS_REVIEW"
    assert result.hte_top_modifier is None
    assert result.anomaly_validity is None


def test_parse_ml_from_json_no_responsive_segments():
    """parse_ml_from_json with empty responsive_segments list."""
    json_data: dict[str, Any] = {
        "ml_result": {
            "overall_verdict": "CLEAN",
            "can_trust_results": True,
            "segments": {
                "responsive_segments": [],
                "overall_recommendation": "No targeted rollout needed.",
            },
        }
    }
    result = parse_ml_from_json(json_data)
    assert result.responsive_segments == []


# ---------------------------------------------------------------------------
# Saas sample experiment integration test (uses precomputed JSON, no API call)
# ---------------------------------------------------------------------------


def test_parse_saas_trial_sample():
    """Parse the precomputed saas_trial JSON and verify all fields hydrate correctly."""
    import json
    from pathlib import Path

    samples_dir = Path(__file__).parent.parent.parent / "app" / "data" / "samples"
    saas_path = samples_dir / "saas_trial.json"
    if not saas_path.exists():
        pytest.skip("saas_trial.json not found")

    with open(saas_path) as f:
        raw = json.load(f)

    precomputed = raw["precomputed_result"]
    stats = parse_stats_from_json(precomputed)
    ml = parse_ml_from_json(precomputed)

    # Stats
    assert stats.is_significant is True
    assert stats.lift_pct > 0
    assert 0 < stats.p_value < 0.05

    # ML
    assert ml.overall_verdict == "CLEAN"
    assert ml.can_trust_results is True
    assert ml.novelty_pattern == "STABLE"
    assert ml.hte_top_modifier is not None  # company_size_x_treat
    assert ml.responsive_segments is not None


def test_fallback_with_saas_sample():
    """build_fallback_interpretation produces valid output from saas_trial data."""
    import json
    from pathlib import Path

    samples_dir = Path(__file__).parent.parent.parent / "app" / "data" / "samples"
    saas_path = samples_dir / "saas_trial.json"
    if not saas_path.exists():
        pytest.skip("saas_trial.json not found")

    with open(saas_path) as f:
        raw = json.load(f)

    precomputed = raw["precomputed_result"]
    stats = parse_stats_from_json(precomputed)
    ml = parse_ml_from_json(precomputed)

    result = build_fallback_interpretation(stats, ml)
    assert isinstance(result, str)
    assert len(result) > 100
    assert "SHIP" in result
    assert "Segment analysis was not run" not in result  # HTE data is present
