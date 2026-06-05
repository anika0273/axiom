"""
Sequential Testing — O'Brien-Fleming for safe interim analysis
=============================================================

Why naive peeking inflates false positives
-------------------------------------------
If you test an experiment repeatedly and stop the moment p < 0.05, you are
not controlling the type I error at 5 %.  Across 10 equally spaced looks at
the same accumulating data, the chance of ever seeing p < 0.05 under the
null hypothesis is roughly 19 % — nearly four times the nominal rate.  Each
look is correlated with every prior look (the same users are in the data),
so the multiple-comparison penalty cannot simply be divided by the number
of looks.

O'Brien-Fleming boundaries: strict early, lenient late
-------------------------------------------------------
O'Brien-Fleming (1979) controls the experiment-wide type I error by
allocating the alpha budget via a *spending function*.  The cumulative alpha
consumed through information fraction t is:

    f(t) = 2 · [1 − Φ(z_{α/2} / √t)]        (two-sided)
    f(t) =     1 − Φ(z_α   / √t)             (one-sided)

The corresponding efficacy boundary at information fraction t is:

    z*(t) = z_{α/2} / √t                      (two-sided)

Key properties
  • Final look (t = 1):   z*(1) ≈ 1.96 — the ordinary normal critical value.
  • t = 0.25:             z*(0.25) ≈ 3.92 — highly conservative.
  • t = 0.10:             z*(0.10) ≈ 6.20 — almost impossible to cross.
  • Sum of incremental alpha over all K looks = exactly α (telescoping).

Crossing the boundary at ANY look controls the experiment-wide false
positive rate at α without any further correction.

Why info fraction matters more than calendar time
--------------------------------------------------
Sequential analysis depends on statistical *information*, not wall-clock
time.  Two experiments may run for the same number of days but collect very
different amounts of evidence.  The information fraction

    t = n_current / n_planned

measures how much of the planned statistical power has been accumulated.
Using t ensures boundaries are evaluated at the right point on the spending
function regardless of the pace of enrolment.

When futility stopping saves sample
-------------------------------------
Not every trial needs to run to its planned end.  If the treatment effect
is near zero after 40 % of data is in, the *conditional power* — the
probability of ever crossing the efficacy boundary given the current trend —
may be very low.  Stopping early for futility avoids wasting budget on an
experiment that is statistically unlikely to succeed.

Futility boundary at information fraction t (non-binding recommendation):

    z_f(t) = max(0, (z_{α/2} − Φ⁻¹(1 − β_f)) · √t)

where β_f = 0.20 is the futility power threshold.  If |z_current| ≤ z_f(t),
the estimated conditional power is below 20 %.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import BaseModel
from scipy.stats import norm

# Conditional power below this threshold triggers a futility recommendation.
_FUTILITY_POWER_THRESHOLD: float = 0.20


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SequentialBoundaries(BaseModel):
    """Precomputed O'Brien-Fleming boundaries for all K planned interim looks.

    Fields
    ------
    alpha_spent_per_look  : incremental type I error consumed at each look;
                            the list sums to exactly ``alpha``.
    z_boundary_per_look   : efficacy critical value at each look; exceeding
                            this (in absolute value for two-sided) stops the
                            trial for a positive finding.
    info_fraction_per_look: t_k = k / K for k = 1 … K (equally spaced).
    futility_boundaries   : if |z_current| ≤ this value, conditional power
                            is below 20 %; consider stopping early.
    total_planned_n       : per-group sample size at the final planned look.
    n_interim_looks       : total number of analyses K (including the final).
    alpha                 : experiment-wide type I error rate.
    two_sided             : True → two-sided test; False → one-sided.
    """

    alpha_spent_per_look: list[float]
    z_boundary_per_look: list[float]
    info_fraction_per_look: list[float]
    futility_boundaries: list[float]
    total_planned_n: int
    n_interim_looks: int
    alpha: float
    two_sided: bool


class SequentialDecision(BaseModel):
    """Decision returned at a single interim look.

    Fields
    ------
    decision              : CONTINUE, STOP_WIN (efficacy boundary crossed),
                            or STOP_LOSE (projected power < 20 %).
    required_z            : O'Brien-Fleming efficacy boundary at the current
                            information fraction.
    current_z             : the z-statistic supplied by the caller.
    info_fraction_complete: fraction of the planned sample collected (clamped
                            to [0, 1] when current_n > total_planned_n).
    interpretation        : plain-English summary of the decision.
    """

    decision: Literal["CONTINUE", "STOP_WIN", "STOP_LOSE"]
    required_z: float
    current_z: float
    info_fraction_complete: float
    interpretation: str


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _critical_z(alpha: float, two_sided: bool) -> float:
    """Normal quantile corresponding to the final-look efficacy boundary."""
    return float(norm.ppf(1.0 - (alpha / 2.0 if two_sided else alpha)))


def _cumulative_alpha_spent(t: float, alpha: float, two_sided: bool) -> float:
    """O'Brien-Fleming cumulative type I error spent by information fraction t.

    f(t) = 2 · [1 − Φ(z_{α/2} / √t)]   (two-sided)
    f(t) =     1 − Φ(z_α     / √t)      (one-sided)

    f(0) is defined as 0 (no data → no alpha spent).
    f(1) = α exactly (total budget consumed at the planned end).
    """
    if t <= 0.0:
        return 0.0
    z_crit = _critical_z(alpha, two_sided)
    tail = float(norm.sf(z_crit / np.sqrt(t)))
    return 2.0 * tail if two_sided else tail


def _obf_z_boundary(t: float, alpha: float, two_sided: bool) -> float:
    """O'Brien-Fleming efficacy boundary at information fraction t.

    z*(t) = z_{α/2} / √t   (two-sided)
    z*(t) = z_α     / √t   (one-sided)

    Args:
        t: Information fraction in (0, 1].  Must be strictly positive.
        alpha: Total type I error budget.
        two_sided: Whether a two-sided boundary is required.

    Returns:
        The critical z-value at this information fraction.
    """
    return _critical_z(alpha, two_sided) / float(np.sqrt(t))


def _futility_z_boundary(t: float, alpha: float, two_sided: bool) -> float:
    """Minimum |z| to avoid a futility stop at information fraction t.

    Derived by solving CP(|z|, t) = _FUTILITY_POWER_THRESHOLD:

        CP(z, t) ≈ Φ(|z| / √t − z_final)    [current-trend conditional power]

    Setting CP = threshold and rearranging:

        |z| < (z_final − Φ⁻¹(1 − threshold)) · √t

    So the futility boundary is:

        z_f(t) = max(0, (z_final − z_{1−β_f}) · √t)

    where z_{1−β_f} = Φ⁻¹(1 − _FUTILITY_POWER_THRESHOLD) ≈ 0.842 for 20 %.

    Args:
        t: Information fraction in (0, 1].
        alpha: Total type I error budget.
        two_sided: Whether a two-sided boundary is required.

    Returns:
        The futility z-threshold at this information fraction.
    """
    z_final = _critical_z(alpha, two_sided)
    z_beta = float(norm.ppf(1.0 - _FUTILITY_POWER_THRESHOLD))
    return float(max(0.0, (z_final - z_beta) * np.sqrt(t)))


def _build_interpretation(
    decision: str,
    current_z: float,
    z_required: float,
    z_futility: float,
    t: float,
    alpha: float,
    two_sided: bool,
) -> str:
    """Return a plain-English summary of a sequential decision."""
    pct = f"{t:.0%}"
    abs_z = abs(current_z)
    z_label = "|z|" if two_sided else "z"
    z_display = abs_z if two_sided else current_z

    if decision == "STOP_WIN":
        direction = "either direction" if two_sided else "treatment direction"
        return (
            f"Crossed the O'Brien-Fleming boundary at {pct} information "
            f"({z_label} = {z_display:.2f} ≥ {z_required:.2f}). "
            f"Statistically significant in the {direction} at α = {alpha:.2f}. "
            f"Safe to stop early and declare a winner."
        )
    if decision == "STOP_LOSE":
        return (
            f"Projected conditional power is below 20% "
            f"({z_label} = {z_display:.2f} ≤ {z_futility:.2f} at {pct} information). "
            f"The experiment is unlikely to detect an effect at the planned "
            f"sample size. Consider stopping early to save sample."
        )
    return (
        f"Continue the experiment "
        f"({z_label} = {z_display:.2f} at {pct} information). "
        f"Sequential boundary requires {z_label} ≥ {z_required:.2f} to stop "
        f"for efficacy; futility boundary is {z_futility:.2f}. "
        f"Gather more data before the next scheduled look."
    )


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def compute_obrien_fleming_boundaries(
    total_planned_n: int,
    n_interim_looks: int,
    alpha: float = 0.05,
    two_sided: bool = True,
) -> SequentialBoundaries:
    """Compute O'Brien-Fleming efficacy and futility boundaries for K interim looks.

    Looks are assumed equally spaced: information fraction t_k = k / K for
    k = 1, …, K.  The final look (k = K, t = 1) is included, so a 10-look
    plan has 9 interim peeks plus the planned final analysis.

    The efficacy boundary at look k is:

        z*(t_k) = z_{α/2} / √t_k

    The cumulative alpha spent through look k is:

        f(t_k) = 2 · [1 − Φ(z_{α/2} / √t_k)]

    and the incremental alpha at look k is Δα_k = f(t_k) − f(t_{k−1}).
    By telescoping, Σ Δα_k = f(1) = α exactly.

    Args:
        total_planned_n: Per-group sample size at the final planned look.
                         Must be positive.
        n_interim_looks: Number of analyses to conduct (K), including the
                         final look.  Must be ≥ 1.
        alpha: Experiment-wide type I error rate.  Must be in (0, 1).
        two_sided: If True, apply a two-sided stopping rule (|z| ≥ boundary).
                   If False, one-sided (z ≥ boundary; detects treatment benefit
                   only).

    Returns:
        SequentialBoundaries with per-look alpha spending, efficacy
        z-boundaries, information fractions, and futility thresholds.

    Raises:
        ValueError: If total_planned_n ≤ 0, n_interim_looks < 1, or
                    alpha ∉ (0, 1).

    Example:
        10 weekly looks with a planned total of 1 000 users per group:

            >>> b = compute_obrien_fleming_boundaries(1000, 10)
            >>> b.z_boundary_per_look[0]   # look 1/10, t=0.1
            6.198...
            >>> b.z_boundary_per_look[-1]  # final look, t=1.0
            1.960...
            >>> sum(b.alpha_spent_per_look)
            0.05
    """
    if total_planned_n <= 0:
        raise ValueError(f"total_planned_n must be positive, got {total_planned_n}.")
    if n_interim_looks < 1:
        raise ValueError(f"n_interim_looks must be ≥ 1, got {n_interim_looks}.")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}.")

    info_fractions = [k / n_interim_looks for k in range(1, n_interim_looks + 1)]

    alpha_spent: list[float] = []
    z_boundaries: list[float] = []
    futility: list[float] = []
    prev_cum = 0.0

    for t in info_fractions:
        cum = _cumulative_alpha_spent(t, alpha, two_sided)
        alpha_spent.append(float(max(0.0, cum - prev_cum)))
        prev_cum = cum
        z_boundaries.append(_obf_z_boundary(t, alpha, two_sided))
        futility.append(_futility_z_boundary(t, alpha, two_sided))

    return SequentialBoundaries(
        alpha_spent_per_look=alpha_spent,
        z_boundary_per_look=z_boundaries,
        info_fraction_per_look=info_fractions,
        futility_boundaries=futility,
        total_planned_n=total_planned_n,
        n_interim_looks=n_interim_looks,
        alpha=alpha,
        two_sided=two_sided,
    )


def evaluate_interim_look(
    current_z: float,
    current_n: int,
    boundaries: SequentialBoundaries,
) -> SequentialDecision:
    """Evaluate whether to stop or continue based on the current z-statistic.

    The O'Brien-Fleming efficacy boundary and futility threshold are computed
    directly from the current information fraction using the closed-form
    formula, so calling this function between planned looks is valid.

    Decision rules (two-sided):
      STOP_WIN  : |z_current| ≥ z*(t)        — boundary crossed; stop for efficacy.
      STOP_LOSE : |z_current| ≤ z_f(t)       — too weak; conditional power < 20%.
      CONTINUE  : z_f(t) < |z_current| < z*(t) — no conclusion yet.

    For one-sided tests replace |z_current| with z_current throughout.  A
    large negative z in a one-sided trial is treated as futile (not as
    evidence of benefit), so it triggers STOP_LOSE rather than STOP_WIN.

    Args:
        current_z: Z-statistic from the current data (treatment − control).
                   Use the signed value; the function applies abs() internally
                   for two-sided tests.
        current_n: Per-group sample size collected so far.  Must be > 0.
                   If current_n > total_planned_n the information fraction is
                   clamped to 1.0 (no error is raised).
        boundaries: Precomputed boundaries from compute_obrien_fleming_boundaries.
                    Provides total_planned_n, alpha, and two_sided settings.

    Returns:
        SequentialDecision with the decision, required z, info fraction, and
        a plain-English interpretation.

    Raises:
        ValueError: If current_n ≤ 0.
    """
    if current_n <= 0:
        raise ValueError(f"current_n must be > 0, got {current_n}.")

    t = min(1.0, current_n / boundaries.total_planned_n)

    z_required = _obf_z_boundary(t, boundaries.alpha, boundaries.two_sided)
    z_futility = _futility_z_boundary(t, boundaries.alpha, boundaries.two_sided)

    # Two-sided: compare |z|.  One-sided: compare z directly.
    test_stat = abs(current_z) if boundaries.two_sided else current_z

    if test_stat >= z_required:
        decision: Literal["CONTINUE", "STOP_WIN", "STOP_LOSE"] = "STOP_WIN"
    elif test_stat <= z_futility:
        decision = "STOP_LOSE"
    else:
        decision = "CONTINUE"

    interpretation = _build_interpretation(
        decision=decision,
        current_z=current_z,
        z_required=z_required,
        z_futility=z_futility,
        t=t,
        alpha=boundaries.alpha,
        two_sided=boundaries.two_sided,
    )

    return SequentialDecision(
        decision=decision,
        required_z=float(round(z_required, 6)),
        current_z=current_z,
        info_fraction_complete=float(round(t, 6)),
        interpretation=interpretation,
    )
