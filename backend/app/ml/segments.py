"""
Automatic segment discovery for A/B experiment analysis.

Finds natural clusters in user feature space, profiles each cluster by its
treatment lift, and produces plain-language rollout recommendations.

Usage::

    analysis = discover_segments(X, treatment, outcome)
    print(analysis.overall_recommendation)
    # "Roll out to segments 0 and 2. Investigate segment 1."
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from app.stats.testing import run_mean_test

logger = logging.getLogger(__name__)

_LOW_SILHOUETTE_THRESHOLD = 0.1
_MIN_SEGMENT_SIZE = 10  # minimum subjects per arm to run a significance test
_MIN_TREATMENT_FRACTION = 0.40  # warn below 40/60 balance
_N_STABILITY_RUNS = 5


@dataclass
class SegmentProfile:
    """Profile of a single discovered segment.

    Attributes:
        id: Zero-based segment index.
        size_pct: Fraction of total subjects in this segment (0–1).
        lift: Mean treatment effect (treatment mean − control mean) for the segment.
        lift_uncertainty: Std deviation of lift across stability runs.
        description: Human-readable prose summary of this segment.
        top_features: Mapping of feature name → (segment mean, global mean).
        significant: True if the within-segment test reaches α=0.05.
        low_confidence: True when the global silhouette score is below the threshold.
    """

    id: int
    size_pct: float
    lift: float
    lift_uncertainty: float
    description: str
    top_features: dict[str, tuple[float, float]]
    significant: bool
    low_confidence: bool = False


@dataclass
class SegmentAnalysis:
    """Result of discover_segments.

    Attributes:
        optimal_k: Number of clusters chosen by silhouette optimisation.
        silhouette_score: Best silhouette score achieved.
        segments: Profiles for every cluster, ordered by id.
        responsive_segments: Ids of segments with significant positive lift.
        stability_scores: Per-segment mean pairwise assignment consistency (0–1).
        overall_recommendation: Plain-English rollout recommendation.
        low_confidence: True when best silhouette score < threshold.
    """

    optimal_k: int
    silhouette_score: float
    segments: list[SegmentProfile]
    responsive_segments: list[int]
    stability_scores: dict[int, float]
    overall_recommendation: str
    low_confidence: bool = False


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _warn_treatment_balance(treatment: pd.Series) -> None:
    """Emit a UserWarning if treatment fraction is outside 40/60."""
    frac = float(treatment.mean())
    if frac < _MIN_TREATMENT_FRACTION or frac > (1.0 - _MIN_TREATMENT_FRACTION):
        warnings.warn(
            f"Treatment fraction {frac:.2%} is outside the 40/60 recommended range. "
            "Per-segment lift estimates may be unreliable.",
            UserWarning,
            stacklevel=3,
        )


def _select_optimal_k(
    X_scaled: np.ndarray,
    max_k: int,
    random_state: int,
) -> tuple[int, float]:
    """Pick the k that maximises silhouette score on a grid k=2..max_k.

    Args:
        X_scaled: Scaled feature matrix.
        max_k: Maximum number of clusters to try.
        random_state: Seed for KMeans.

    Returns:
        (best_k, best_silhouette_score)
    """
    n = X_scaled.shape[0]
    # k must be < n_samples; cap sensibly.
    effective_max = min(max_k, n - 1)
    if effective_max < 2:
        return 2, 0.0

    best_k, best_score = 2, -1.0
    for k in range(2, effective_max + 1):
        km = KMeans(n_clusters=k, n_init=10, random_state=random_state)
        labels = km.fit_predict(X_scaled)
        # silhouette_score requires > 1 unique label.
        if len(np.unique(labels)) < 2:
            continue
        score = float(silhouette_score(X_scaled, labels, sample_size=min(5000, n)))
        logger.debug("k=%d silhouette=%.4f", k, score)
        if score > best_score:
            best_k, best_score = k, score

    return best_k, best_score


def _compute_segment_lift(
    mask: np.ndarray,
    treatment: pd.Series,
    outcome: pd.Series,
) -> tuple[float, bool]:
    """Run run_mean_test for one segment; return (lift_abs, is_significant).

    Falls back to (0.0, False) when either arm is too small for the test.

    Args:
        mask: Boolean array selecting subjects in this segment.
        treatment: Full treatment Series.
        outcome: Full outcome Series.

    Returns:
        (lift_abs, is_significant)
    """
    seg_treatment = treatment[mask]
    seg_outcome = outcome[mask]

    ctrl = seg_outcome[seg_treatment == 0].values
    trt = seg_outcome[seg_treatment == 1].values

    if len(ctrl) < _MIN_SEGMENT_SIZE or len(trt) < _MIN_SEGMENT_SIZE:
        logger.warning(
            "Segment too small for significance test (ctrl=%d, trt=%d); "
            "returning lift=0, significant=False.",
            len(ctrl),
            len(trt),
        )
        return 0.0, False

    result = run_mean_test(ctrl, trt)
    return float(result.lift_abs), bool(result.is_significant)


def _segment_lift_uncertainty(
    X_scaled: np.ndarray,
    treatment: pd.Series,
    outcome: pd.Series,
    k: int,
    random_state: int,
    n_runs: int,
) -> dict[int, list[float]]:
    """Collect per-segment lift across n_runs KMeans refits.

    Segments are matched across runs by nearest-centroid distance so that
    segment numbering is consistent with the primary fit.

    Args:
        X_scaled: Scaled feature matrix.
        treatment: Binary treatment Series.
        outcome: Outcome Series.
        k: Number of clusters.
        random_state: Base seed (each run uses random_state + i).
        n_runs: Number of independent refits.

    Returns:
        Dict mapping segment id → list of lift values across runs.
    """
    lifts: dict[int, list[float]] = {i: [] for i in range(k)}

    # Primary cluster centroids (used for matching).
    primary = KMeans(n_clusters=k, n_init=10, random_state=random_state)
    primary_labels = primary.fit_predict(X_scaled)
    primary_centroids = primary.cluster_centers_

    for run in range(n_runs):
        km = KMeans(n_clusters=k, n_init=10, random_state=random_state + run + 1)
        run_labels = km.fit_predict(X_scaled)

        # Map run cluster ids → primary cluster ids by nearest centroid.
        id_map: dict[int, int] = {}
        for run_id in range(k):
            run_centroid = km.cluster_centers_[run_id]
            dists = np.linalg.norm(primary_centroids - run_centroid, axis=1)
            id_map[run_id] = int(np.argmin(dists))

        for run_id, primary_id in id_map.items():
            mask = run_labels == run_id
            lift, _ = _compute_segment_lift(mask, treatment, outcome)
            lifts[primary_id].append(lift)

    return lifts


def _assignment_consistency(
    X_scaled: np.ndarray,
    k: int,
    random_state: int,
    n_runs: int,
) -> dict[int, float]:
    """Estimate per-segment stability as mean pairwise assignment overlap.

    For each pair of runs, computes the fraction of subjects assigned to the
    same (matched) cluster.  The mean across all pairs is the stability score.

    Args:
        X_scaled: Scaled feature matrix.
        k: Number of clusters.
        random_state: Base seed.
        n_runs: Number of independent refits.

    Returns:
        Dict mapping segment id → mean pairwise consistency in [0, 1].
    """
    primary = KMeans(n_clusters=k, n_init=10, random_state=random_state)
    primary_labels = primary.fit_predict(X_scaled)
    primary_centroids = primary.cluster_centers_

    all_mapped: list[np.ndarray] = [primary_labels]
    for run in range(1, n_runs):
        km = KMeans(n_clusters=k, n_init=10, random_state=random_state + run)
        run_labels = km.fit_predict(X_scaled)
        mapped = np.empty_like(run_labels)
        for run_id in range(k):
            run_centroid = km.cluster_centers_[run_id]
            dists = np.linalg.norm(primary_centroids - run_centroid, axis=1)
            primary_id = int(np.argmin(dists))
            mapped[run_labels == run_id] = primary_id
        all_mapped.append(mapped)

    stability: dict[int, float] = {}
    for seg_id in range(k):
        pair_scores: list[float] = []
        for a, b in combinations(range(len(all_mapped)), 2):
            in_seg_a = all_mapped[a] == seg_id
            in_seg_b = all_mapped[b] == seg_id
            # Jaccard-style: intersection / union.
            union = np.logical_or(in_seg_a, in_seg_b).sum()
            if union == 0:
                pair_scores.append(1.0)
            else:
                pair_scores.append(
                    float(np.logical_and(in_seg_a, in_seg_b).sum() / union)
                )
        stability[seg_id] = float(np.mean(pair_scores)) if pair_scores else 0.0

    return stability


def _top_features_for_segment(
    X: pd.DataFrame,
    mask: np.ndarray,
    n_top: int = 3,
) -> dict[str, tuple[float, float]]:
    """Return top-n features by within-cluster vs global mean deviation.

    Args:
        X: Original (unscaled) feature DataFrame.
        mask: Boolean mask for this segment.
        n_top: How many features to return.

    Returns:
        {feature_name: (segment_mean, global_mean)} for the top features.
    """
    global_means = X.mean()
    seg_means = X[mask].mean()
    deviation = (seg_means - global_means).abs().sort_values(ascending=False)
    top_cols = deviation.head(n_top).index.tolist()
    return {col: (float(seg_means[col]), float(global_means[col])) for col in top_cols}


def _describe_segment(
    seg_id: int,
    size_pct: float,
    lift: float,
    significant: bool,
    top_features: dict[str, tuple[float, float]],
    low_confidence: bool,
) -> str:
    """Compose a human-readable prose description of the segment.

    Args:
        seg_id: Segment index.
        size_pct: Fraction of users in this segment.
        lift: Absolute lift estimate.
        significant: Whether the lift is statistically significant.
        top_features: {feature: (seg_mean, global_mean)}.
        low_confidence: Whether clustering confidence is low.

    Returns:
        Prose description string.
    """
    size_label = (
        "large" if size_pct > 0.35 else "mid-sized" if size_pct > 0.15 else "small"
    )
    pct_str = f"{size_pct * 100:.0f}%"
    lift_str = f"{lift:+.3f}"
    sig_str = "significant" if significant else "not significant"

    if top_features:
        feat_name, (seg_val, glob_val) = next(iter(top_features.items()))
        direction = "above" if seg_val > glob_val else "below"
        feat_desc = (
            f" with {feat_name} {direction} average ({seg_val:.2f} vs {glob_val:.2f})"
        )
    else:
        feat_desc = ""

    conf_note = " [low clustering confidence]" if low_confidence else ""
    return (
        f"Segment {seg_id}: {size_label} group ({pct_str} of users){feat_desc}. "
        f"Lift: {lift_str} ({sig_str}).{conf_note}"
    )


def _build_overall_recommendation(
    segments: list[SegmentProfile],
    overall_lift: float,
) -> str:
    """Build a plain-English rollout recommendation.

    Args:
        segments: All segment profiles.
        overall_lift: ATE across all subjects.

    Returns:
        Recommendation string.
    """
    rollout = [s.id for s in segments if s.significant and s.lift > 0]
    investigate = [s.id for s in segments if not s.significant]
    avoid = [s.id for s in segments if s.significant and s.lift <= 0]

    parts: list[str] = []
    if rollout:
        parts.append(
            f"Roll out to segment{'s' if len(rollout) > 1 else ''} "
            f"{', '.join(str(i) for i in rollout)}."
        )
    if investigate:
        parts.append(
            f"Investigate segment{'s' if len(investigate) > 1 else ''} "
            f"{', '.join(str(i) for i in investigate)} (inconclusive)."
        )
    if avoid:
        parts.append(
            f"Avoid segment{'s' if len(avoid) > 1 else ''} "
            f"{', '.join(str(i) for i in avoid)} (negative lift)."
        )
    if not parts:
        parts.append("No segments with clear positive lift; consider running longer.")

    sign = "+" if overall_lift >= 0 else ""
    parts.append(f"Overall ATE: {sign}{overall_lift:.3f}.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def discover_segments(
    X: pd.DataFrame,
    treatment: pd.Series,
    outcome: pd.Series,
    max_k: int = 8,
    random_state: int = 42,
) -> SegmentAnalysis:
    """Discover user segments with heterogeneous treatment response.

    Scales features, selects k via silhouette optimisation, profiles each
    cluster with per-segment significance tests, and produces a rollout
    recommendation.

    Assumes X contains only numeric features; the caller must pre-process
    any categorical columns before calling this function.

    Args:
        X: User feature matrix (numeric only; pre-processed by caller).
        treatment: Binary Series (0 = control, 1 = treatment), same index as X.
        outcome: Continuous outcome Series, same index as X.
        max_k: Maximum number of clusters to evaluate. Default 8.
        random_state: Seed for all stochastic operations. Default 42.

    Returns:
        SegmentAnalysis with profiles, stability scores, and a recommendation.

    Raises:
        ValueError: If inputs have mismatched lengths or X is empty.
    """
    if len(X) != len(treatment) or len(X) != len(outcome):
        raise ValueError(
            f"X ({len(X)}), treatment ({len(treatment)}), and outcome ({len(outcome)}) "
            "must have the same length."
        )
    if len(X) == 0:
        raise ValueError("X must not be empty.")

    X = X.reset_index(drop=True)
    treatment = treatment.reset_index(drop=True)
    outcome = outcome.reset_index(drop=True)

    _warn_treatment_balance(treatment)

    # 1. Scale features.
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X.values.astype(float))

    # 2. Silhouette-optimal k.
    optimal_k, best_sil = _select_optimal_k(X_scaled, max_k, random_state)
    low_confidence = best_sil < _LOW_SILHOUETTE_THRESHOLD

    if low_confidence:
        logger.warning(
            "Best silhouette score %.4f < %.2f; using k=2 with low_confidence flag.",
            best_sil,
            _LOW_SILHOUETTE_THRESHOLD,
        )
        optimal_k = 2

    # 3. Final KMeans fit.
    km = KMeans(n_clusters=optimal_k, n_init=10, random_state=random_state)
    labels = km.fit_predict(X_scaled)

    # 4. Lift uncertainty across stability runs.
    lift_runs = _segment_lift_uncertainty(
        X_scaled, treatment, outcome, optimal_k, random_state, _N_STABILITY_RUNS
    )

    # 5. Assignment stability scores.
    stability_scores = _assignment_consistency(
        X_scaled, optimal_k, random_state, _N_STABILITY_RUNS
    )

    # 6. Per-segment profiles.
    n_total = len(X)

    # Compute overall ATE for the recommendation.
    ctrl_all = outcome[treatment == 0].values
    trt_all = outcome[treatment == 1].values
    if len(ctrl_all) >= _MIN_SEGMENT_SIZE and len(trt_all) >= _MIN_SEGMENT_SIZE:
        overall_lift = float(run_mean_test(ctrl_all, trt_all).lift_abs)
    else:
        overall_lift = 0.0

    segments: list[SegmentProfile] = []
    for seg_id in range(optimal_k):
        mask = labels == seg_id
        size_pct = float(mask.sum() / n_total)

        lift, significant = _compute_segment_lift(mask, treatment, outcome)
        lift_runs_for_seg = lift_runs.get(seg_id, [])
        lift_uncertainty = (
            float(np.std(lift_runs_for_seg)) if lift_runs_for_seg else 0.0
        )

        top_features = _top_features_for_segment(X, mask)
        description = _describe_segment(
            seg_id, size_pct, lift, significant, top_features, low_confidence
        )

        segments.append(
            SegmentProfile(
                id=seg_id,
                size_pct=size_pct,
                lift=lift,
                lift_uncertainty=lift_uncertainty,
                description=description,
                top_features=top_features,
                significant=significant,
                low_confidence=low_confidence,
            )
        )

    responsive_segments = [s.id for s in segments if s.significant and s.lift > 0]
    recommendation = _build_overall_recommendation(segments, overall_lift)

    return SegmentAnalysis(
        optimal_k=optimal_k,
        silhouette_score=best_sil,
        segments=segments,
        responsive_segments=responsive_segments,
        stability_scores=stability_scores,
        overall_recommendation=recommendation,
        low_confidence=low_confidence,
    )
