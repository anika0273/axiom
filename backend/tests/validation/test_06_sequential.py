"""Validation 6 — O'Brien-Fleming sequential boundaries.

External reference
------------------
The O'Brien-Fleming efficacy boundary at information fraction t is:

    z*(t) = z_{α/2} / √t   (two-sided)

where z_{α/2} = norm.ppf(1 − α/2).

The cumulative alpha spent through t is:

    f(t) = 2 · [1 − Φ(z_{α/2} / √t)]

The incremental alpha at look k is f(t_k) − f(t_{k−1}), and the sum over all
K looks must equal α exactly (telescoping).

The futility boundary is:

    z_f(t) = max(0, (z_{α/2} − z_{1−β_f}) · √t)

where β_f = 0.20 (20% conditional-power threshold).

Scenarios
---------
SEQ1  Boundary values at 5 equally-spaced looks — compare computed z*(t_k)
      against the closed-form formula.  Tolerance: 0.001.
SEQ2  Alpha budget — sum of incremental alpha over all looks ≈ α.
      Tolerance: 0.001.
SEQ3  Monotonicity — early boundary must be strictly greater than late boundary
      (z*(0.2) > z*(0.4) > … > z*(1.0)).
SEQ4  Decision logic — STOP_WIN, STOP_LOSE, CONTINUE at representative z values.

Failure diagnosis
-----------------
• z* deviation > 0.001: formula uses wrong z_crit (check α vs α/2).
• Alpha sum off: cumulative spending function f(t) or telescoping wrong.
• Monotonicity violated: z* not divided by sqrt(t) — constant boundary used.
• Decision mismatch: comparison operators or sign convention wrong.
"""

from __future__ import annotations

import math

from scipy.stats import norm

from app.stats.sequential import (
    compute_obrien_fleming_boundaries,
    evaluate_interim_look,
)
from tests.validation._report import record

_MODULE = "sequential"
_TOL = 0.001


def _ref_z_boundary(t: float, alpha: float, two_sided: bool) -> float:
    """Reference OBF efficacy boundary: z_crit / sqrt(t)."""
    z_crit = float(norm.ppf(1.0 - (alpha / 2.0 if two_sided else alpha)))
    return z_crit / math.sqrt(t)


def _ref_cum_alpha(t: float, alpha: float, two_sided: bool) -> float:
    """Reference OBF cumulative alpha spent at fraction t."""
    if t <= 0.0:
        return 0.0
    z_crit = float(norm.ppf(1.0 - (alpha / 2.0 if two_sided else alpha)))
    tail = float(norm.sf(z_crit / math.sqrt(t)))
    return 2.0 * tail if two_sided else tail


def test_seq1_boundary_values_five_looks() -> None:
    """SEQ1: z*(t_k) matches closed-form formula for K=5 equally-spaced looks.

    t_k = k/5 for k = 1..5.  Expected boundaries (α=0.05, two-sided):
    t=0.2 → z* ≈ 4.382, t=0.4 → z* ≈ 3.099, t=0.6 → z* ≈ 2.530,
    t=0.8 → z* ≈ 2.191, t=1.0 → z* ≈ 1.960.
    """
    alpha = 0.05
    K = 5
    boundaries = compute_obrien_fleming_boundaries(
        total_planned_n=5000,
        n_interim_looks=K,
        alpha=alpha,
        two_sided=True,
    )

    t_values = [k / K for k in range(1, K + 1)]
    ref_z = [_ref_z_boundary(t, alpha, True) for t in t_values]
    obs_z = boundaries.z_boundary_per_look

    all_pass = True
    failures: list[str] = []
    for k, (ref, obs, t) in enumerate(zip(ref_z, obs_z, t_values), 1):
        delta = abs(obs - ref)
        if delta > _TOL:
            all_pass = False
            failures.append(
                f"look {k} (t={t:.1f}): ref={ref:.4f}, obs={obs:.4f}, Δ={delta:.4f}"
            )

    likely = ""
    if not all_pass:
        likely = (
            "z_crit may use wrong tail (α instead of α/2) or sqrt is missing. "
            "Check _obf_z_boundary: should be z_crit / sqrt(t)."
        )

    summary = (
        f"z*=[{', '.join(f'{z:.3f}' for z in obs_z)}] vs "
        f"ref=[{', '.join(f'{z:.3f}' for z in ref_z)}]"
    )

    record(
        module=_MODULE,
        scenario="SEQ1: z*(t_k) at K=5 looks, α=0.05, two-sided",
        expected=f"z*={[round(z, 3) for z in ref_z]}",
        observed=f"z*={[round(z, 3) for z in obs_z]}",
        delta=f"max Δ={max(abs(a-b) for a,b in zip(obs_z, ref_z)):.4f}",
        tolerance=f"≤{_TOL}",
        passed=all_pass,
        likely_cause=likely,
        notes=summary,
    )

    assert all_pass, f"SEQ1 boundary deviations: {'; '.join(failures)}"


def test_seq2_alpha_budget_sums_to_alpha() -> None:
    """SEQ2: Sum of incremental alpha over K looks must equal α within tolerance.

    Tests that the telescoping property f(t_K) = α holds and that the
    per-look incremental spending sums to the total budget.
    """
    for K in [3, 5, 10]:
        alpha = 0.05
        boundaries = compute_obrien_fleming_boundaries(
            total_planned_n=10000, n_interim_looks=K, alpha=alpha, two_sided=True
        )
        total_spent = sum(boundaries.alpha_spent_per_look)
        delta = abs(total_spent - alpha)
        passed = delta <= _TOL

        likely = ""
        if not passed:
            likely = (
                f"Alpha sum = {total_spent:.6f} ≠ {alpha}. "
                "Check that prev_cum is updated correctly in the loop and that "
                "f(t_K=1.0) equals the full alpha budget."
            )

        record(
            module=_MODULE,
            scenario=f"SEQ2: alpha budget K={K}, α={alpha}",
            expected=f"sum(α_spent) = {alpha}",
            observed=f"sum(α_spent) = {total_spent:.6f}",
            delta=f"{delta:.2e}",
            tolerance=f"≤{_TOL}",
            passed=passed,
            likely_cause=likely,
        )

        assert passed, (
            f"SEQ2 K={K}: alpha sum = {total_spent:.6f} (expected {alpha}, "
            f"Δ={delta:.2e}). {likely}"
        )


def test_seq3_monotonicity_early_stricter() -> None:
    """SEQ3: Early boundaries must be strictly larger than late boundaries.

    z*(t) = z_crit / sqrt(t) is strictly decreasing in t, so the boundary at
    any early look must exceed the boundary at any later look.
    """
    boundaries = compute_obrien_fleming_boundaries(
        total_planned_n=8000, n_interim_looks=8, alpha=0.05, two_sided=True
    )
    z_vals = boundaries.z_boundary_per_look
    violations = [
        (k, z_vals[k - 1], z_vals[k])
        for k in range(1, len(z_vals))
        if z_vals[k - 1] <= z_vals[k]
    ]
    passed = len(violations) == 0

    likely = ""
    if not passed:
        likely = (
            "Boundary is not decreasing — z*(t) must equal z_crit/sqrt(t), "
            "not a constant value.  Check that info fractions t_k are correctly "
            "computed as k/K."
        )

    record(
        module=_MODULE,
        scenario="SEQ3: monotonicity K=8, α=0.05",
        expected="z*[k] > z*[k+1] for all k (strictly decreasing)",
        observed=f"z*=[{', '.join(f'{z:.3f}' for z in z_vals)}]",
        delta=f"{len(violations)} violation(s)",
        tolerance="0 violations",
        passed=passed,
        likely_cause=likely,
    )

    assert passed, f"SEQ3 monotonicity violations: {violations}"

    # Also validate: final boundary ≈ z_0.025 = 1.96
    final_z = z_vals[-1]
    ref_final = float(norm.ppf(0.975))
    assert (
        abs(final_z - ref_final) <= _TOL
    ), f"Final boundary {final_z:.4f} should ≈ 1.960 (z_0.025={ref_final:.4f})"


def test_seq4_decision_logic() -> None:
    """SEQ4: STOP_WIN / STOP_LOSE / CONTINUE at representative z values.

    At t=0.50 for K=4 looks, α=0.05 (two-sided):
    z*(0.5) = 1.960 / sqrt(0.5) ≈ 2.772.

    Test three representative z values:
      • z = 3.5 > z*(0.5) → STOP_WIN
      • z = 0.3 near zero → STOP_LOSE (conditional power < 20%)
      • z = 1.5 between boundaries → CONTINUE
    """
    alpha = 0.05
    K = 4
    boundaries = compute_obrien_fleming_boundaries(
        total_planned_n=4000, n_interim_looks=K, alpha=alpha, two_sided=True
    )

    # current_n = 2000 → info fraction = 2000/4000 = 0.5
    current_n = 2000

    cases = [
        ("stop_win", 3.5, "STOP_WIN", "z > efficacy boundary"),
        ("continue", 1.5, "CONTINUE", "z between futility and efficacy"),
        ("stop_lose", 0.05, "STOP_LOSE", "z near zero → futility"),
    ]

    for case_id, z_val, expected_dec, rationale in cases:
        decision = evaluate_interim_look(z_val, current_n, boundaries)
        passed = decision.decision == expected_dec

        likely = ""
        if not passed:
            likely = (
                f"Expected {expected_dec} for z={z_val} at t=0.50 "
                f"but got {decision.decision}.  "
                f"Efficacy boundary ≈ {decision.required_z:.3f}.  "
                "Check that abs(z) is compared for two-sided tests."
            )

        record(
            module=_MODULE,
            scenario=f"SEQ4: {case_id}, z={z_val}, t=0.50 (K=4)",
            expected=expected_dec,
            observed=decision.decision,
            delta="exact match required",
            tolerance="exact",
            passed=passed,
            likely_cause=likely,
            notes=f"{rationale}; required_z≈{decision.required_z:.3f}",
        )

        assert passed, (
            f"SEQ4 {case_id}: z={z_val} → expected {expected_dec}, "
            f"got {decision.decision}.  required_z={decision.required_z:.3f}.  "
            f"{likely}"
        )
