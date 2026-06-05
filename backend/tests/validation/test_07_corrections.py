"""Validation 7 — Multiple comparison corrections (known-answer tests).

External reference
------------------
All expected values are computed by hand using the published algorithms and
cross-checked with statsmodels.stats.multitest.multipletests.

Known-answer case (COR1)
------------------------
p = [0.008, 0.016, 0.030, 0.060], n=4, α=0.05 (already sorted ascending)

Bonferroni threshold = 0.05/4 = 0.0125:
  • 0.008 < 0.0125 → REJECT
  • 0.016 ≥ 0.0125 → accept   → n_rejected = 1

Holm step-down thresholds = [0.0125, 0.01667, 0.025, 0.05]:
  • k=0: 0.008 < 0.0125 → REJECT
  • k=1: 0.016 < 0.01667 → REJECT
  • k=2: 0.030 < 0.025? No → stop   → n_rejected = 2

BH (step-up):  q[k] = min(p[k]*n/(k+1), 1.0)
  raw_q = [0.032, 0.032, 0.040, 0.060]
  cummin from right = [0.032, 0.032, 0.040, 0.060]
  reject where q ≤ 0.05: k=0 (0.032 ✓), k=1 (0.032 ✓), k=2 (0.040 ✓), k=3 (0.060 ✗)
  → n_rejected = 3

Result: Bonferroni=1, Holm=2, BH=3.  Power ordering: BH > Holm > Bonferroni.

Failure diagnosis
-----------------
• Bonferroni count wrong → threshold is α/n not α (n scaling missing).
• Holm count wrong → step-down threshold α/(n−k) or cummax monotonicity wrong.
• BH count wrong → step-up logic (largest k) or cummin-from-right missing.
• reject_mask sign → strict < for Bonferroni/Holm, non-strict ≤ for BH.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest
from statsmodels.stats.multitest import multipletests

from app.stats.corrections import apply_multiple_correction, compare_corrections
from tests.validation._report import record

_MODULE = "corrections"
_P_TOL = 0.001  # corrected p-value tolerance
_ALPHA = 0.05


# ---------------------------------------------------------------------------
# Reference helper using statsmodels
# ---------------------------------------------------------------------------


def _statsmodels_ref(
    p_values: list[float], method: str
) -> tuple[np.ndarray, np.ndarray]:
    """Return (reject_mask, corrected_p) from statsmodels multipletests."""
    sm_method = {
        "bonferroni": "bonferroni",
        "holm_bonferroni": "holm",
        "fdr_bh": "fdr_bh",
    }
    reject, p_adj, _, _ = multipletests(
        p_values, alpha=_ALPHA, method=sm_method[method]
    )
    return np.array(reject, dtype=bool), np.array(p_adj, dtype=float)


# ---------------------------------------------------------------------------
# Core known-answer scenarios
# ---------------------------------------------------------------------------


def test_cor1_known_answer_all_three() -> None:
    """COR1: Known-answer case — p=[0.008,0.016,0.030,0.060].

    Manual calculation verified above:
    Bonferroni=1 rejection, Holm=2 rejections, BH=3 rejections.
    """
    p_values = [0.008, 0.016, 0.030, 0.060]

    expected = {"bonferroni": 1, "holm_bonferroni": 2, "fdr_bh": 3}
    expected_masks = {
        "bonferroni": [True, False, False, False],
        "holm_bonferroni": [True, True, False, False],
        "fdr_bh": [True, True, True, False],
    }

    all_pass = True
    for method, exp_n in expected.items():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = apply_multiple_correction(np.array(p_values), method=method)

        obs_n = result.n_rejected
        obs_mask = list(result.reject_mask)
        exp_mask = expected_masks[method]

        pass_n = obs_n == exp_n
        pass_mask = obs_mask == exp_mask

        likely = ""
        if not pass_n or not pass_mask:
            all_pass = False
            if method == "bonferroni":
                likely = "Bonferroni threshold = α/n = 0.0125; only p[0]=0.008 passes."
            elif method == "holm_bonferroni":
                likely = (
                    "Holm threshold at k=1 is α/(n−1) = 0.01667; p[1]=0.016 < 0.01667."
                )
            else:
                likely = "BH cummin-from-right: q[2]=0.040 ≤ 0.05, so k=2 is the largest reject."

        record(
            module=_MODULE,
            scenario=f"COR1: known-answer {method}, p=[0.008,0.016,0.030,0.060]",
            expected=f"n_rejected={exp_n}, mask={exp_mask}",
            observed=f"n_rejected={obs_n}, mask={obs_mask}",
            delta=f"n_diff={abs(obs_n-exp_n)}, mask_diff={sum(a!=b for a,b in zip(obs_mask,exp_mask))}",
            tolerance="exact match",
            passed=pass_n and pass_mask,
            likely_cause=likely,
        )

        assert (
            pass_n
        ), f"COR1 {method}: expected {exp_n} rejections, got {obs_n}. {likely}"
        assert (
            pass_mask
        ), f"COR1 {method}: expected mask {exp_mask}, got {obs_mask}. {likely}"


def test_cor2_bh_more_powerful_than_bonferroni() -> None:
    """COR2: BH rejects more hypotheses than Bonferroni on a permissive p-value set.

    p = [0.005, 0.020, 0.035, 0.045, 0.049], n=5, α=0.05.

    BH finds largest k where p[k] ≤ (k+1)/5 × 0.05:
    k=4: 0.049 ≤ 0.05 → reject all 5.
    Bonferroni threshold = 0.01: only p[0]=0.005 passes.
    """
    p_values = [0.005, 0.020, 0.035, 0.045, 0.049]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        bh_result = apply_multiple_correction(np.array(p_values), method="fdr_bh")
    bonf_result = apply_multiple_correction(np.array(p_values), method="bonferroni")

    bh_n = bh_result.n_rejected
    bonf_n = bonf_result.n_rejected
    passed = bh_n > bonf_n

    likely = ""
    if not passed:
        likely = (
            f"Expected BH ({bh_n}) > Bonferroni ({bonf_n}). "
            "BH step-up should accept all 5 because p[4]=0.049 ≤ 5/5×0.05=0.050. "
            "Check cummin-from-right enforces step-up: if largest k has q≤α, "
            "all lower ranks are also rejected."
        )

    record(
        module=_MODULE,
        scenario="COR2: BH > Bonferroni, p=[0.005,0.020,0.035,0.045,0.049]",
        expected=f"BH ({bh_n}) > Bonferroni ({bonf_n})",
        observed=f"BH={bh_n}, Bonferroni={bonf_n}",
        delta=f"diff={bh_n - bonf_n}",
        tolerance="BH > Bonferroni (strict)",
        passed=passed,
        likely_cause=likely,
        notes="BH step-up: p[4]=0.049 ≤ 0.050 triggers reject-all.",
    )

    assert passed, f"COR2: BH={bh_n} should > Bonferroni={bonf_n}. {likely}"


def test_cor3_holm_between_bonferroni_and_bh() -> None:
    """COR3: Holm is between Bonferroni and BH — Bonferroni ≤ Holm ≤ BH.

    Uses COR1 input: Bonferroni=1, Holm=2, BH=3 confirms ordering.
    """
    p_values = [0.008, 0.016, 0.030, 0.060]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        bh_result = apply_multiple_correction(np.array(p_values), method="fdr_bh")
    bonf_result = apply_multiple_correction(np.array(p_values), method="bonferroni")
    holm_result = apply_multiple_correction(
        np.array(p_values), method="holm_bonferroni"
    )

    n_b, n_h, n_bh = (
        bonf_result.n_rejected,
        holm_result.n_rejected,
        bh_result.n_rejected,
    )
    passed = n_b <= n_h <= n_bh

    likely = ""
    if not passed:
        likely = (
            "Power ordering violated: Bonferroni ≤ Holm ≤ BH must always hold. "
            "Holm is uniformly more powerful than Bonferroni by the step-down "
            "property.  BH controls FDR (not FWER), permitting more rejections."
        )

    record(
        module=_MODULE,
        scenario="COR3: power ordering Bonferroni≤Holm≤BH",
        expected=f"Bonferroni≤Holm≤BH",
        observed=f"Bonferroni={n_b}, Holm={n_h}, BH={n_bh}",
        delta=f"ordering {'OK' if passed else 'VIOLATED'}",
        tolerance="Bonferroni≤Holm≤BH",
        passed=passed,
        likely_cause=likely,
    )

    assert (
        passed
    ), f"COR3 power ordering: Bonferroni={n_b}, Holm={n_h}, BH={n_bh}. {likely}"


def test_cor4_corrected_p_values_against_statsmodels() -> None:
    """COR4: Corrected p-values match statsmodels.stats.multitest.multipletests.

    Uses a diverse p-value set to validate the adjusted p computations.
    """
    p_values = [0.001, 0.012, 0.043, 0.089, 0.156]

    for method in ("bonferroni", "holm_bonferroni", "fdr_bh"):
        ref_reject, ref_p = _statsmodels_ref(p_values, method)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = apply_multiple_correction(np.array(p_values), method=method)

        max_p_diff = float(np.max(np.abs(result.corrected_p - ref_p)))
        mask_diff = int(np.sum(result.reject_mask != ref_reject))
        passed = max_p_diff <= _P_TOL and mask_diff == 0

        likely = ""
        if not passed:
            if mask_diff > 0:
                likely = (
                    f"{mask_diff} reject-mask entry(ies) differ from statsmodels. "
                    "Check the comparison operator: Bonferroni/Holm use < (strict), "
                    "BH uses ≤ (non-strict)."
                )
            else:
                likely = (
                    f"Corrected p-values differ by up to {max_p_diff:.4f}. "
                    "Check monotonicity enforcement (cummax for Holm, cummin for BH)."
                )

        record(
            module=_MODULE,
            scenario=f"COR4: corrected p vs statsmodels, {method}",
            expected=f"corrected_p≈statsmodels, mask matches",
            observed=f"max_Δp={max_p_diff:.4e}, mask_diffs={mask_diff}",
            delta=f"max_Δp={max_p_diff:.4e}",
            tolerance=f"Δp≤{_P_TOL}, 0 mask diffs",
            passed=passed,
            likely_cause=likely,
        )

        assert (
            passed
        ), f"COR4 {method}: max_Δp={max_p_diff:.4e}, mask_diffs={mask_diff}. {likely}"


def test_cor5_single_test_no_correction() -> None:
    """COR5: Single test — all methods are no-ops.

    With n=1, Bonferroni multiplier=1, Holm multiplier=1, BH rank=1/1.
    All corrected p-values must equal the original p-value.
    """
    p_single = [0.032]

    for method in ("bonferroni", "holm_bonferroni", "fdr_bh"):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = apply_multiple_correction(np.array(p_single), method=method)

        obs_p = float(result.corrected_p[0])
        delta = abs(obs_p - p_single[0])
        passed = delta <= 1e-9  # must be exact

        likely = ""
        if not passed:
            likely = f"n=1 single test must leave p unchanged; got {obs_p:.6f} not {p_single[0]}."

        record(
            module=_MODULE,
            scenario=f"COR5: single test no-op, {method}",
            expected=f"corrected_p={p_single[0]}",
            observed=f"corrected_p={obs_p:.6f}",
            delta=f"{delta:.2e}",
            tolerance="exact (n=1 no-op)",
            passed=passed,
            likely_cause=likely,
        )

        assert (
            passed
        ), f"COR5 {method}: single test corrected_p={obs_p} ≠ {p_single[0]}. {likely}"
