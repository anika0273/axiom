"""
Multiple comparison correction for A/B experiments with multiple metrics.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The multiple comparison problem
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When an A/B experiment measures m independent metrics at α = 0.05, the
expected number of false positives under the null is 0.05 × m.  For 20
metrics, one false positive is expected by chance alone.

Two types of error control are available:

    FWER (Family-Wise Error Rate): P(at least one false positive) ≤ α
        Bonferroni and Holm-Bonferroni guarantee this regardless of how
        many true nulls are present.

    FDR (False Discovery Rate): E[false positives / total rejections] ≤ α
        Benjamini-Hochberg controls FDR at α.  When m is large and many
        H₀ are true, FDR control is substantially more powerful.

Comparison table
────────────────────────────────────────────────────────────────────────────
Method           Error control  Power    When to use
────────────────────────────────────────────────────────────────────────────
Bonferroni       FWER           Lowest   1–5 pre-specified primary metrics,
                                          confirmatory trials
Holm-Bonferroni  FWER           Medium   ≤ 20 metrics, FWER required; always
                                          at least as good as Bonferroni
Benjamini-H.     FDR            Highest  ≥ 10 metrics, exploratory analysis;
                                          FDR ≤ α under PRDS assumption
────────────────────────────────────────────────────────────────────────────

A/B testing example: 5 metrics at α = 0.05
───────────────────────────────────────────
Raw p-values: p = [0.001, 0.012, 0.043, 0.089, 0.156]

Bonferroni (threshold = α/5 = 0.010):
    Only p[0] = 0.001 passes.  Power cost: ~40%.

Holm step-down (thresholds = 0.010, 0.0125, 0.017, 0.025, 0.050):
    p[0] = 0.001 < 0.010 → reject
    p[1] = 0.012 < 0.0125 → reject  (gains one extra vs Bonferroni)
    p[2] = 0.043 < 0.017? No → stop.  Power cost: ~30%.

BH FDR (thresholds = 0.010, 0.020, 0.030, 0.040, 0.050):
    Largest k with p[k] ≤ (k+1)/5 × 0.05: k=1 (p[1]=0.012 ≤ 0.020).
    Reject all with rank ≤ 1 → same 2 rejections here; FDR ≤ 5%.
"""

from __future__ import annotations

import warnings
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CorrectionResult(BaseModel):
    """Result of applying a single multiple comparison correction method.

    Fields
    ------
    method           : "bonferroni", "holm_bonferroni", or "fdr_bh".
    original_p       : Input p-values in original (caller) order.
    corrected_p      : Adjusted p-values in original order.
                       Bonferroni / Holm: FWER-adjusted (Holm-adjusted).
                       BH: FDR q-values.
    reject_mask      : True for each hypothesis rejected at alpha.
    n_rejected       : Number of hypotheses rejected.
    fwer_upper_bound : Upper bound on family-wise error rate.
                       Equals alpha for Bonferroni and Holm.
                       For BH this is a Bonferroni-style bound min(n×α, 1).
    fdr_upper_bound  : Upper bound on false discovery rate.
                       Equals alpha for all three methods
                       (FDR ≤ FWER ≤ α for FWER methods).
    interpretation   : Plain-English summary.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    method: str
    original_p: np.ndarray
    corrected_p: np.ndarray
    reject_mask: np.ndarray
    n_rejected: int
    fwer_upper_bound: float
    fdr_upper_bound: float
    interpretation: str


class CorrectionComparison(BaseModel):
    """Side-by-side comparison of all three correction methods.

    Fields
    ------
    bonferroni : Result under Bonferroni correction.
    holm       : Result under Holm-Bonferroni step-down correction.
    fdr_bh     : Result under Benjamini-Hochberg FDR correction.
    summary    : Plain-English comparison, e.g.
                 "BH most powerful (3 sig), Bonferroni most conservative (1 sig)".
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    bonferroni: CorrectionResult
    holm: CorrectionResult
    fdr_bh: CorrectionResult
    summary: str


class CorrectionRecommendation(BaseModel):
    """Recommendation for which correction method to use.

    Fields
    ------
    method                 : "bonferroni", "holm_bonferroni", or "fdr_bh".
    reasoning              : Explanation of the recommendation.
    expected_power_loss_pct: Approximate power reduction relative to testing
                             each hypothesis at the uncorrected α.
    """

    method: str
    reasoning: str
    expected_power_loss_pct: float


# ---------------------------------------------------------------------------
# Private helpers — validation and interpretation
# ---------------------------------------------------------------------------


def _validate_p_values(p_values: np.ndarray) -> None:
    """Validate that p_values is a non-empty, finite array with all values in [0, 1].

    Args:
        p_values: Candidate p-value array.

    Raises:
        ValueError: If p_values is empty, contains NaN/inf, or has values outside [0, 1].
    """
    if len(p_values) == 0:
        raise ValueError("p_values must be non-empty.")
    if np.any(np.isnan(p_values)) or np.any(np.isinf(p_values)):
        raise ValueError("p_values must not contain NaN or infinity.")
    if np.any(p_values < 0.0) or np.any(p_values > 1.0):
        raise ValueError("All p_values must be in [0, 1].")


def _bonferroni_interpretation(n: int, n_rejected: int, alpha: float) -> str:
    """Build a plain-English summary for a Bonferroni result."""
    if n == 1:
        return (
            f"Single test — Bonferroni correction is a no-op. "
            f"{n_rejected} hypothesis rejected at α = {alpha}."
        )
    threshold = alpha / n
    return (
        f"Bonferroni: {n_rejected}/{n} hypotheses rejected (threshold = {threshold:.4f}). "
        f"FWER ≤ {alpha} guaranteed. Strictest control; expect some power loss for large n."
    )


def _holm_interpretation(n: int, n_rejected: int, alpha: float) -> str:
    """Build a plain-English summary for a Holm result."""
    if n == 1:
        return (
            f"Single test — Holm correction is a no-op. "
            f"{n_rejected} hypothesis rejected at α = {alpha}."
        )
    return (
        f"Holm step-down: {n_rejected}/{n} hypotheses rejected. "
        f"FWER ≤ {alpha} guaranteed. Uniformly more powerful than Bonferroni."
    )


def _bh_interpretation(n: int, n_rejected: int, alpha: float) -> str:
    """Build a plain-English summary for a BH result."""
    if n == 1:
        return (
            f"Single test — BH correction is a no-op. "
            f"{n_rejected} hypothesis rejected at α = {alpha}."
        )
    expected_fp = n_rejected * alpha
    return (
        f"Benjamini-Hochberg FDR: {n_rejected}/{n} hypotheses rejected. "
        f"FDR ≤ {alpha} (expected false positives among rejections ≤ {expected_fp:.2f}). "
        f"Assumes positive regression dependence (PRDS) among test statistics."
    )


def _build_comparison_summary(
    b: CorrectionResult,
    h: CorrectionResult,
    f: CorrectionResult,
) -> str:
    """Build a summary string comparing the three correction results."""
    methods = [
        ("Bonferroni", b.n_rejected),
        ("Holm", h.n_rejected),
        ("BH", f.n_rejected),
    ]
    by_power = sorted(methods, key=lambda x: x[1], reverse=True)
    most_powerful = by_power[0]
    most_conservative = by_power[-1]

    if most_powerful[1] == most_conservative[1]:
        return (
            f"All methods agree: {b.n_rejected} rejection(s). "
            f"Bonferroni={b.n_rejected}, Holm={h.n_rejected}, BH={f.n_rejected}."
        )

    p_word = "rejection" if most_powerful[1] == 1 else "rejections"
    c_word = "rejection" if most_conservative[1] == 1 else "rejections"
    return (
        f"{most_powerful[0]} most powerful ({most_powerful[1]} {p_word}), "
        f"{most_conservative[0]} most conservative ({most_conservative[1]} {c_word}). "
        f"Bonferroni={b.n_rejected}, Holm={h.n_rejected}, BH={f.n_rejected}."
    )


# ---------------------------------------------------------------------------
# Core correction implementations (manual — no scipy/statsmodels)
# ---------------------------------------------------------------------------


def _apply_bonferroni(p_values: np.ndarray, alpha: float) -> CorrectionResult:
    """Bonferroni correction: p_adj[i] = min(p[i] × n, 1.0).

    Controls FWER by requiring each test to clear the α/n threshold,
    derived from a union bound over n independent tests.  Reject when
    p_adj[i] < α (strict inequality; ties at the boundary are not rejected).

    Args:
        p_values: Validated p-value array (length n).
        alpha: Significance level in (0, 1).

    Returns:
        CorrectionResult with method="bonferroni".
    """
    n = len(p_values)
    corrected = np.minimum(p_values * n, 1.0)
    reject_mask = corrected < alpha
    n_rejected = int(np.sum(reject_mask))

    return CorrectionResult(
        method="bonferroni",
        original_p=p_values.copy(),
        corrected_p=corrected,
        reject_mask=reject_mask,
        n_rejected=n_rejected,
        fwer_upper_bound=float(alpha),
        fdr_upper_bound=float(alpha),
        interpretation=_bonferroni_interpretation(n, n_rejected, alpha),
    )


def _apply_holm(p_values: np.ndarray, alpha: float) -> CorrectionResult:
    """Holm step-down correction.

    Sort p ascending.  For rank k (0-indexed), reject while p[k] < α/(n−k).
    At the first non-rejection, all subsequent (larger) p-values are accepted.

    Adjusted p-values (in sorted order): p_adj[k] = min(p[k] × (n−k), 1.0).
    Monotonicity is enforced via a cumulative maximum (step-down property:
    no lower-ranked hypothesis can have a larger adjusted p than a higher one).

    Holm is uniformly at least as powerful as Bonferroni and controls the
    same FWER at α.

    Args:
        p_values: Validated p-value array (length n).
        alpha: Significance level in (0, 1).

    Returns:
        CorrectionResult with method="holm_bonferroni".
    """
    n = len(p_values)
    sort_idx = np.argsort(p_values, kind="stable")
    p_sorted = p_values[sort_idx]

    # Step multipliers: n, n-1, ..., 1 for sorted ranks 0 .. n-1.
    multipliers = n - np.arange(n, dtype=float)
    raw_adj = np.minimum(p_sorted * multipliers, 1.0)
    # Cumulative max enforces step-down monotonicity.
    adj_sorted: np.ndarray = np.maximum.accumulate(raw_adj)

    corrected_p = np.empty(n)
    corrected_p[sort_idx] = adj_sorted

    reject_mask = corrected_p < alpha
    n_rejected = int(np.sum(reject_mask))

    return CorrectionResult(
        method="holm_bonferroni",
        original_p=p_values.copy(),
        corrected_p=corrected_p,
        reject_mask=reject_mask,
        n_rejected=n_rejected,
        fwer_upper_bound=float(alpha),
        fdr_upper_bound=float(alpha),
        interpretation=_holm_interpretation(n, n_rejected, alpha),
    )


def _apply_bh(p_values: np.ndarray, alpha: float) -> CorrectionResult:
    """Benjamini-Hochberg FDR correction.

    Sort p ascending.  Find the largest rank k (0-indexed) where
    p[k] ≤ (k+1)/n × α, then reject all hypotheses at ranks 0 .. k
    (step-up property).

    Adjusted p-values (q-values): q[k] = min(p[k] × n/(k+1), 1.0).
    Monotonicity is enforced via a cumulative minimum from the right
    (step-up: lower-ranked hypotheses inherit the constraint from
    higher-ranked ones).

    Controls FDR at α assuming PRDS (positive regression dependence on
    subsets) among the test statistics.  For arbitrary dependence, use
    the more conservative BY correction.

    Args:
        p_values: Validated p-value array (length n).
        alpha: Target FDR level in (0, 1).

    Returns:
        CorrectionResult with method="fdr_bh".
    """
    n = len(p_values)
    sort_idx = np.argsort(p_values, kind="stable")
    p_sorted = p_values[sort_idx]

    ranks = np.arange(1, n + 1, dtype=float)
    raw_adj = np.minimum(p_sorted * n / ranks, 1.0)
    # Cumulative min from the right enforces step-up monotonicity.
    adj_sorted: np.ndarray = np.minimum.accumulate(raw_adj[::-1])[::-1]

    corrected_p = np.empty(n)
    corrected_p[sort_idx] = adj_sorted

    # BH threshold is ≤ (non-strict), so reject when q-value ≤ alpha.
    reject_mask = corrected_p <= alpha
    n_rejected = int(np.sum(reject_mask))

    # FWER is not controlled by BH; provide a Bonferroni-style upper bound.
    fwer_bound = float(min(n * alpha, 1.0))

    return CorrectionResult(
        method="fdr_bh",
        original_p=p_values.copy(),
        corrected_p=corrected_p,
        reject_mask=reject_mask,
        n_rejected=n_rejected,
        fwer_upper_bound=fwer_bound,
        fdr_upper_bound=float(alpha),
        interpretation=_bh_interpretation(n, n_rejected, alpha),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_multiple_correction(
    p_values: np.ndarray,
    method: Literal["bonferroni", "holm_bonferroni", "fdr_bh"],
    alpha: float = 0.05,
) -> CorrectionResult:
    """Apply a multiple comparison correction to a set of p-values.

    Algorithms are implemented from scratch without scipy or statsmodels:

        Bonferroni : p_adj[i] = min(p[i] × n, 1.0); reject if p_adj < α.
        Holm       : Sort ascending; reject while p[k] < α/(n−k); step-down.
        BH         : Sort ascending; reject while p[k] ≤ (k+1)/n × α; step-up.

    Args:
        p_values: Array of p-values, shape (n_tests,).  All values must be
                  in [0, 1] with no NaN or infinity.  May be unsorted.
        method:   "bonferroni", "holm_bonferroni", or "fdr_bh".
        alpha:    Significance level in (0, 1).  Default 0.05.

    Returns:
        CorrectionResult with corrected p-values and reject_mask in the
        same order as the input p_values.

    Raises:
        ValueError: If p_values is empty, contains invalid values, or
                    alpha is not in (0, 1).

    Note:
        BH controls FDR at α under PRDS (positive regression dependence
        on subsets).  For arbitrary dependence, use the BY correction.
        A UserWarning is emitted as a reminder when BH is applied to
        more than one test.
    """
    p = np.asarray(p_values, dtype=float)
    _validate_p_values(p)
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}.")

    if method == "bonferroni":
        return _apply_bonferroni(p, alpha)
    if method == "holm_bonferroni":
        return _apply_holm(p, alpha)
    if method == "fdr_bh":
        if len(p) > 1:
            warnings.warn(
                "BH correction assumes positive regression dependence (PRDS) among "
                "test statistics. For negatively dependent tests, use BY correction.",
                UserWarning,
                stacklevel=2,
            )
        return _apply_bh(p, alpha)
    raise ValueError(
        f"Unknown method {method!r}. Choose from 'bonferroni', 'holm_bonferroni', 'fdr_bh'."
    )


def compare_corrections(
    p_values: np.ndarray,
    alpha: float = 0.05,
) -> CorrectionComparison:
    """Apply all three corrections and compare results side-by-side.

    Useful for understanding the power trade-off before committing to a
    method.  The summary field highlights which method is most/least
    powerful for the given p-value set.

    Args:
        p_values: Array of p-values, shape (n_tests,).  All values must be
                  in [0, 1] with no NaN or infinity.
        alpha:    Significance level in (0, 1).  Default 0.05.

    Returns:
        CorrectionComparison with all three results and a summary string.

    Raises:
        ValueError: If p_values or alpha are invalid.
    """
    p = np.asarray(p_values, dtype=float)
    _validate_p_values(p)
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}.")

    bonferroni_result = _apply_bonferroni(p, alpha)
    holm_result = _apply_holm(p, alpha)
    bh_result = _apply_bh(p, alpha)

    return CorrectionComparison(
        bonferroni=bonferroni_result,
        holm=holm_result,
        fdr_bh=bh_result,
        summary=_build_comparison_summary(bonferroni_result, holm_result, bh_result),
    )


def recommend_correction(
    n_tests: int,
    context: Literal["confirmatory", "exploratory", "production"],
    prior_signals: int = 1,
) -> CorrectionRecommendation:
    """Recommend a multiple comparison correction method for the given context.

    Decision logic:

        confirmatory : FWER control required.  Bonferroni is the default
                       because it is simple, interpretable, and expected by
                       most statistical reviewers.  For n > 10, Holm would
                       gain power while maintaining the same guarantee, but
                       confirmatory settings rarely have that many primaries.

        exploratory  : FDR control via BH.  Maximises discovery power; some
                       false positives are acceptable in an exploratory phase.

        production   : FWER control.  Bonferroni for small metric sets
                       (≤ 10), Holm for larger ones where power matters.

    The expected_power_loss_pct is an approximation based on the reduction in
    effective α per test.  Actual power loss depends on the true effect sizes
    and sample sizes of the experiment.

    Args:
        n_tests:       Number of hypotheses to test simultaneously.  Must be ≥ 1.
        context:       "confirmatory", "exploratory", or "production".
        prior_signals: Number of metrics expected a priori to show a real
                       effect.  Currently informational; future versions may
                       use this to weight FDR priors.

    Returns:
        CorrectionRecommendation with method, reasoning, and power loss estimate.

    Raises:
        ValueError: If n_tests < 1.
    """
    if n_tests < 1:
        raise ValueError(f"n_tests must be ≥ 1, got {n_tests}.")

    if n_tests == 1:
        return CorrectionRecommendation(
            method="bonferroni",
            reasoning="Single test — no multiple comparison correction needed; Bonferroni is a no-op.",
            expected_power_loss_pct=0.0,
        )

    # Approximate fractional power loss scaling: ~(1 − 1/n) at full conservatism.
    base_loss = 100.0 * (1.0 - 1.0 / n_tests)

    if context == "confirmatory":
        method = "bonferroni"
        reasoning = (
            f"Confirmatory setting with {n_tests} pre-specified hypotheses. "
            f"Bonferroni controls FWER strictly and is simple to pre-register. "
            f"False positives in a confirmatory trial carry high cost, "
            f"justifying the conservative threshold α/{n_tests} = "
            f"{0.05 / n_tests:.4f} (at α = 0.05)."
        )
        power_loss = min(95.0, base_loss)

    elif context == "exploratory":
        method = "fdr_bh"
        reasoning = (
            f"Exploratory setting with {n_tests} hypotheses. "
            f"Benjamini-Hochberg maximises discovery power while bounding "
            f"the expected false discovery rate at α. "
            f"Some false positives are acceptable in an exploratory phase "
            f"because findings will be validated before acting."
        )
        power_loss = min(95.0, base_loss * 0.35)

    else:  # production
        if n_tests <= 10:
            method = "bonferroni"
            reasoning = (
                f"Production setting with {n_tests} metrics. "
                f"Bonferroni provides strict FWER control and is easy to "
                f"communicate to stakeholders. Appropriate for small metric "
                f"sets where the power cost is manageable."
            )
            power_loss = min(95.0, base_loss)
        else:
            method = "holm_bonferroni"
            reasoning = (
                f"Production setting with {n_tests} metrics. "
                f"Holm provides the same FWER guarantee as Bonferroni but is "
                f"uniformly more powerful via the step-down procedure. "
                f"Preferred over Bonferroni when the metric count is large "
                f"and power matters."
            )
            power_loss = min(95.0, base_loss * 0.75)

    return CorrectionRecommendation(
        method=method,
        reasoning=reasoning,
        expected_power_loss_pct=round(power_loss, 1),
    )
