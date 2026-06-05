"""Tests for backend/app/ml/segments.py — automatic segment discovery."""

from __future__ import annotations

import warnings
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from app.ml.segments import (
    SegmentAnalysis,
    SegmentProfile,
    _assignment_consistency,
    _build_overall_recommendation,
    _compute_segment_lift,
    _describe_segment,
    _segment_lift_uncertainty,
    _top_features_for_segment,
    _warn_treatment_balance,
    discover_segments,
)

# ---------------------------------------------------------------------------
# Synthetic data factories
# ---------------------------------------------------------------------------


def _make_three_clusters(
    n_per_cluster: int = 200, seed: int = 0
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Three well-separated clusters with distinct treatment responses."""
    rng = np.random.default_rng(seed)

    # Cluster 0: low x0, low x1 → weak response
    # Cluster 1: high x0, low x1 → strong response
    # Cluster 2: mid x0, high x1 → moderate response
    centers = [(0.0, 0.0), (5.0, 0.0), (2.5, 5.0)]
    X_parts, t_parts, y_parts = [], [], []

    for i, (c0, c1) in enumerate(centers):
        x0 = rng.normal(c0, 0.4, n_per_cluster)
        x1 = rng.normal(c1, 0.4, n_per_cluster)
        t = (rng.random(n_per_cluster) < 0.5).astype(float)
        lift_coef = [0.1, 0.8, 0.4][i]
        y = x0 * 0.2 + x1 * 0.1 + t * lift_coef + rng.normal(0, 0.2, n_per_cluster)
        X_parts.append(pd.DataFrame({"x0": x0, "x1": x1}))
        t_parts.append(pd.Series(t))
        y_parts.append(pd.Series(y))

    X = pd.concat(X_parts, ignore_index=True)
    t = pd.concat(t_parts, ignore_index=True)
    y = pd.concat(y_parts, ignore_index=True)
    return X, t, y


def _make_random_noise(
    n: int = 300, seed: int = 7
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Standard Gaussian noise — no natural cluster structure."""
    rng = np.random.default_rng(seed)
    X = pd.DataFrame({"x0": rng.standard_normal(n), "x1": rng.standard_normal(n)})
    t = pd.Series((rng.random(n) < 0.5).astype(float))
    y = pd.Series(rng.standard_normal(n))
    return X, t, y


# ---------------------------------------------------------------------------
# Return-type and structure
# ---------------------------------------------------------------------------


def test_discover_segments_returns_segment_analysis():
    X, t, y = _make_three_clusters()
    result = discover_segments(X, t, y)
    assert isinstance(result, SegmentAnalysis)


def test_number_of_segment_profiles_equals_optimal_k():
    X, t, y = _make_three_clusters()
    result = discover_segments(X, t, y)
    assert len(result.segments) == result.optimal_k


def test_each_profile_is_segment_profile():
    X, t, y = _make_three_clusters()
    result = discover_segments(X, t, y)
    for seg in result.segments:
        assert isinstance(seg, SegmentProfile)


def test_segment_ids_are_contiguous_from_zero():
    X, t, y = _make_three_clusters()
    result = discover_segments(X, t, y)
    ids = [s.id for s in result.segments]
    assert sorted(ids) == list(range(result.optimal_k))


def test_size_pcts_sum_to_one():
    X, t, y = _make_three_clusters()
    result = discover_segments(X, t, y)
    total = sum(s.size_pct for s in result.segments)
    assert abs(total - 1.0) < 1e-6


def test_stability_scores_keys_match_segment_ids():
    X, t, y = _make_three_clusters()
    result = discover_segments(X, t, y)
    assert set(result.stability_scores.keys()) == set(range(result.optimal_k))


def test_stability_scores_in_zero_one():
    X, t, y = _make_three_clusters()
    result = discover_segments(X, t, y)
    for seg_id, score in result.stability_scores.items():
        assert 0.0 <= score <= 1.0, f"Segment {seg_id} stability {score} out of range"


# ---------------------------------------------------------------------------
# 3-cluster discovery
# ---------------------------------------------------------------------------


def test_three_cluster_data_discovers_k_three():
    """Well-separated 3-cluster data should yield optimal_k == 3."""
    X, t, y = _make_three_clusters(n_per_cluster=250, seed=0)
    result = discover_segments(X, t, y, max_k=6)
    assert (
        result.optimal_k == 3
    ), f"Expected k=3 for 3-cluster data, got {result.optimal_k}"


def test_three_cluster_silhouette_is_reasonable():
    """3-cluster silhouette should be above the low-confidence threshold."""
    X, t, y = _make_three_clusters(n_per_cluster=250, seed=0)
    result = discover_segments(X, t, y, max_k=6)
    assert result.silhouette_score > 0.1


def test_three_cluster_not_low_confidence():
    X, t, y = _make_three_clusters(n_per_cluster=250, seed=0)
    result = discover_segments(X, t, y, max_k=6)
    assert not result.low_confidence


# ---------------------------------------------------------------------------
# Stable clusters → stability score > 0.8
# ---------------------------------------------------------------------------


def test_stable_clusters_have_high_stability():
    """Tight, well-separated clusters should have stability > 0.8."""
    X, t, y = _make_three_clusters(n_per_cluster=300, seed=1)
    result = discover_segments(X, t, y, max_k=6)
    for seg_id, score in result.stability_scores.items():
        assert (
            score > 0.8
        ), f"Segment {seg_id} stability {score:.3f} expected > 0.8 for stable clusters"


# ---------------------------------------------------------------------------
# Low silhouette → low_confidence flagged
# (mocked so behaviour is tested deterministically, not via random data luck)
# ---------------------------------------------------------------------------


def test_low_silhouette_flags_low_confidence():
    """When _select_optimal_k returns silhouette < 0.1, low_confidence must be set."""
    X, t, y = _make_random_noise(n=400, seed=99)
    with patch("app.ml.segments._select_optimal_k", return_value=(2, 0.05)):
        result = discover_segments(X, t, y, max_k=6)
    assert result.low_confidence, "Expected low_confidence=True when silhouette < 0.1"


def test_low_silhouette_forces_k_two():
    """Low-confidence fallback must use k=2 regardless of what _select_optimal_k suggested."""
    X, t, y = _make_random_noise(n=400, seed=99)
    # Return k=5 with low silhouette — the fallback should override to k=2.
    with patch("app.ml.segments._select_optimal_k", return_value=(5, 0.04)):
        result = discover_segments(X, t, y, max_k=6)
    assert result.optimal_k == 2


def test_low_silhouette_propagates_to_segment_profiles():
    """Each SegmentProfile should carry low_confidence=True when the global flag is set."""
    X, t, y = _make_random_noise(n=400, seed=99)
    with patch("app.ml.segments._select_optimal_k", return_value=(2, 0.05)):
        result = discover_segments(X, t, y, max_k=6)
    for seg in result.segments:
        assert seg.low_confidence, f"Segment {seg.id} missing low_confidence flag"


# ---------------------------------------------------------------------------
# Stats engine integration — significance testing is delegated
# ---------------------------------------------------------------------------


def test_per_segment_significance_uses_stats_engine():
    """_compute_segment_lift must call run_mean_test, not reimplement it."""
    rng = np.random.default_rng(42)
    n = 200
    treatment = pd.Series((rng.random(n) < 0.5).astype(float))
    outcome = pd.Series(rng.standard_normal(n))
    mask = np.ones(n, dtype=bool)

    with patch("app.ml.segments.run_mean_test") as mock_test:
        from app.stats.testing import TestResult

        mock_test.return_value = TestResult(
            is_significant=True,
            p_value=0.01,
            confidence_interval=(-0.1, 0.5),
            lift_pct=5.0,
            lift_abs=0.2,
            test_statistic=2.5,
            test_type="t-test",
            sample_warnings=[],
            interpretation="significant",
        )
        lift, sig = _compute_segment_lift(mask, treatment, outcome)
        mock_test.assert_called_once()

    assert lift == pytest.approx(0.2)
    assert sig is True


def test_discover_segments_uses_stats_engine_for_per_segment_tests():
    """Full pipeline should invoke run_mean_test at least once per segment."""
    X, t, y = _make_three_clusters(n_per_cluster=100)
    with patch(
        "app.ml.segments.run_mean_test",
        wraps=__import__("app.stats.testing", fromlist=["run_mean_test"]).run_mean_test,
    ) as mock_test:
        result = discover_segments(X, t, y, max_k=4)
        # At minimum: one call per segment + one for overall ATE.
        assert mock_test.call_count >= result.optimal_k


# ---------------------------------------------------------------------------
# overall_recommendation is a non-empty string
# ---------------------------------------------------------------------------


def test_overall_recommendation_nonempty():
    X, t, y = _make_three_clusters()
    result = discover_segments(X, t, y)
    assert isinstance(result.overall_recommendation, str)
    assert len(result.overall_recommendation) > 0


def test_overall_recommendation_mentions_overall_ate():
    X, t, y = _make_three_clusters()
    result = discover_segments(X, t, y)
    assert "Overall ATE" in result.overall_recommendation


# ---------------------------------------------------------------------------
# Segment descriptions are human-readable (not "cluster_0" etc.)
# ---------------------------------------------------------------------------


def test_segment_descriptions_are_prose():
    X, t, y = _make_three_clusters()
    result = discover_segments(X, t, y)
    for seg in result.segments:
        assert (
            "cluster_" not in seg.description.lower()
        ), f"Description should be human-readable, got: {seg.description}"
        assert len(seg.description) > 20


def test_segment_descriptions_contain_lift():
    X, t, y = _make_three_clusters()
    result = discover_segments(X, t, y)
    for seg in result.segments:
        assert "Lift" in seg.description or "lift" in seg.description


# ---------------------------------------------------------------------------
# top_features content
# ---------------------------------------------------------------------------


def test_top_features_keys_are_column_names():
    X, t, y = _make_three_clusters()
    result = discover_segments(X, t, y)
    valid_cols = set(X.columns)
    for seg in result.segments:
        for col in seg.top_features:
            assert col in valid_cols


def test_top_features_values_are_float_pairs():
    X, t, y = _make_three_clusters()
    result = discover_segments(X, t, y)
    for seg in result.segments:
        for col, (seg_mean, glob_mean) in seg.top_features.items():
            assert isinstance(seg_mean, float)
            assert isinstance(glob_mean, float)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_raises_on_mismatched_lengths():
    X = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    t = pd.Series([0.0, 1.0])
    y = pd.Series([0.1, 0.2, 0.3])
    with pytest.raises(ValueError, match="same length"):
        discover_segments(X, t, y)


def test_raises_on_empty_input():
    X = pd.DataFrame({"x": pd.Series([], dtype=float)})
    t = pd.Series([], dtype=float)
    y = pd.Series([], dtype=float)
    with pytest.raises(ValueError, match="empty"):
        discover_segments(X, t, y)


# ---------------------------------------------------------------------------
# Treatment balance warning
# ---------------------------------------------------------------------------


def test_warns_on_imbalanced_treatment():
    rng = np.random.default_rng(0)
    n = 400
    X = pd.DataFrame({"x": rng.standard_normal(n)})
    t = pd.Series((rng.random(n) < 0.25).astype(float))  # ~25% treatment
    y = pd.Series(rng.standard_normal(n))
    with pytest.warns(UserWarning, match="40/60 recommended range"):
        discover_segments(X, t, y)


def test_no_warning_on_balanced_treatment():
    rng = np.random.default_rng(1)
    n = 400
    X = pd.DataFrame({"x": rng.standard_normal(n)})
    t = pd.Series((rng.random(n) < 0.5).astype(float))
    y = pd.Series(rng.standard_normal(n))
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        discover_segments(X, t, y)  # should not raise


# ---------------------------------------------------------------------------
# _top_features_for_segment unit tests
# ---------------------------------------------------------------------------


def test_top_features_returns_at_most_three():
    X = pd.DataFrame({f"f{i}": np.arange(10, dtype=float) * i for i in range(6)})
    mask = np.array([True] * 5 + [False] * 5)
    result = _top_features_for_segment(X, mask, n_top=3)
    assert len(result) <= 3


def test_top_features_highest_deviation_first():
    X = pd.DataFrame(
        {
            "big": [10.0, 10.0, 10.0, 0.0, 0.0],  # large deviation in first 3
            "small": [1.0, 1.0, 1.0, 1.0, 1.0],  # no deviation
        }
    )
    mask = np.array([True, True, True, False, False])
    result = _top_features_for_segment(X, mask, n_top=2)
    assert list(result.keys())[0] == "big"


# ---------------------------------------------------------------------------
# _build_overall_recommendation unit tests
# ---------------------------------------------------------------------------


def test_recommendation_includes_rollout_for_positive_significant():
    segs = [
        SegmentProfile(0, 0.5, 0.3, 0.05, "desc", {}, True),
        SegmentProfile(1, 0.5, -0.1, 0.05, "desc", {}, True),
    ]
    rec = _build_overall_recommendation(segs, overall_lift=0.1)
    assert "Roll out to segment 0" in rec


def test_recommendation_includes_avoid_for_negative_significant():
    segs = [
        SegmentProfile(0, 0.5, -0.3, 0.05, "desc", {}, True),
        SegmentProfile(1, 0.5, 0.1, 0.05, "desc", {}, False),
    ]
    rec = _build_overall_recommendation(segs, overall_lift=-0.1)
    assert "Avoid segment 0" in rec


def test_recommendation_includes_investigate_for_insignificant():
    segs = [
        SegmentProfile(0, 0.5, 0.1, 0.05, "desc", {}, False),
        SegmentProfile(1, 0.5, 0.1, 0.05, "desc", {}, False),
    ]
    rec = _build_overall_recommendation(segs, overall_lift=0.05)
    assert "Investigate" in rec


# ---------------------------------------------------------------------------
# _compute_segment_lift — small segment fallback
# ---------------------------------------------------------------------------


def test_compute_lift_returns_zero_for_small_segment():
    treatment = pd.Series([0.0] * 5 + [1.0] * 5)
    outcome = pd.Series(np.arange(10, dtype=float))
    mask = np.array([True] * 4 + [False] * 6)  # only 4 in segment
    lift, sig = _compute_segment_lift(mask, treatment, outcome)
    assert lift == 0.0
    assert sig is False


# ---------------------------------------------------------------------------
# _describe_segment — no raw cluster labels
# ---------------------------------------------------------------------------


def test_describe_segment_uses_prose_not_cluster_label():
    desc = _describe_segment(
        seg_id=2,
        size_pct=0.3,
        lift=0.15,
        significant=True,
        top_features={"age": (35.0, 30.0)},
        low_confidence=False,
    )
    assert "cluster_2" not in desc
    assert "Segment 2" in desc


# ---------------------------------------------------------------------------
# Single-feature dataset
# ---------------------------------------------------------------------------


def test_single_feature_dataset_returns_valid_analysis():
    """discover_segments handles a dataset with exactly one input feature."""
    rng = np.random.default_rng(42)
    n = 300
    x = np.concatenate([rng.normal(-3.0, 0.3, n // 2), rng.normal(3.0, 0.3, n // 2)])
    t = pd.Series((rng.random(n) < 0.5).astype(float))
    y = pd.Series(x * 0.3 + t * 0.2 + rng.normal(0, 0.2, n))
    X = pd.DataFrame({"x": x})
    result = discover_segments(X, t, y)
    assert isinstance(result, SegmentAnalysis)
    assert len(result.segments) >= 2
    for seg in result.segments:
        assert isinstance(seg, SegmentProfile)


def test_single_feature_top_features_key_is_valid_column():
    """Single-feature top_features must reference the one column that exists."""
    rng = np.random.default_rng(42)
    n = 300
    x = np.concatenate([rng.normal(-3.0, 0.3, n // 2), rng.normal(3.0, 0.3, n // 2)])
    t = pd.Series((rng.random(n) < 0.5).astype(float))
    y = pd.Series(x * 0.3 + t * 0.2 + rng.normal(0, 0.2, n))
    X = pd.DataFrame({"x": x})
    result = discover_segments(X, t, y)
    for seg in result.segments:
        for col in seg.top_features:
            assert col == "x", f"Expected column 'x', got {col!r}"


# ---------------------------------------------------------------------------
# Perfectly balanced clusters (equal size)
# ---------------------------------------------------------------------------


def test_perfectly_balanced_clusters_size_pcts_sum_to_one():
    """Two tight equal-count clusters; size_pcts must still sum to 1.0."""
    rng = np.random.default_rng(7)
    n_per = 200
    x0_a = rng.normal(-5.0, 0.2, n_per)
    x0_b = rng.normal(5.0, 0.2, n_per)
    x1 = rng.normal(0.0, 0.2, n_per * 2)
    x0 = np.concatenate([x0_a, x0_b])
    t = pd.Series((rng.random(n_per * 2) < 0.5).astype(float))
    y = pd.Series(x0 * 0.2 + t * 0.3 + rng.normal(0, 0.1, n_per * 2))
    X = pd.DataFrame({"x0": x0, "x1": x1})
    result = discover_segments(X, t, y, max_k=4)
    total = sum(s.size_pct for s in result.segments)
    assert abs(total - 1.0) < 1e-6


def test_perfectly_balanced_clusters_each_segment_nonempty():
    """Every discovered segment must contain at least some subjects (size_pct > 0)."""
    rng = np.random.default_rng(7)
    n_per = 200
    x0_a = rng.normal(-5.0, 0.2, n_per)
    x0_b = rng.normal(5.0, 0.2, n_per)
    x1 = rng.normal(0.0, 0.2, n_per * 2)
    x0 = np.concatenate([x0_a, x0_b])
    t = pd.Series((rng.random(n_per * 2) < 0.5).astype(float))
    y = pd.Series(x0 * 0.2 + t * 0.3 + rng.normal(0, 0.1, n_per * 2))
    X = pd.DataFrame({"x0": x0, "x1": x1})
    result = discover_segments(X, t, y, max_k=4)
    for seg in result.segments:
        assert seg.size_pct > 0.0, f"Segment {seg.id} has zero subjects"


# ---------------------------------------------------------------------------
# overall_recommendation is actionable (mentions specific segments)
# ---------------------------------------------------------------------------


def test_overall_recommendation_mentions_specific_segments_or_fallback():
    """Recommendation must reference specific segment IDs, or use the no-lift fallback."""
    import re

    X, t, y = _make_three_clusters()
    result = discover_segments(X, t, y)
    rec = result.overall_recommendation
    # Matches "segment 0", "segments 0, 1, 2", "Investigate segment 1", etc.
    has_segment_id = re.search(r"segments?\s+\d", rec, re.IGNORECASE) is not None
    has_fallback = "no segments" in rec.lower()
    assert has_segment_id or has_fallback, (
        f"Recommendation must be actionable (mention specific segments or fallback), "
        f"got: {rec!r}"
    )


def test_overall_recommendation_always_contains_ate_value():
    """Recommendation must always end with 'Overall ATE: ±N.NNN.' for machine readability."""
    import re

    X, t, y = _make_three_clusters()
    result = discover_segments(X, t, y)
    assert re.search(
        r"Overall ATE: [+-]?\d+\.\d+\.", result.overall_recommendation
    ), f"Expected 'Overall ATE: ...' in recommendation, got: {result.overall_recommendation!r}"
