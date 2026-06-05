"""Validation 8 — Engine integration (full-pipeline consistency).

Scenario: Online shopping A/B test
-----------------------------------
A retailer tests a redesigned checkout button.

Design:
  • Metric type: proportion (conversion rate)
  • Control: 3 000 users, 300 conversions (10.0%)
  • Treatment: 3 000 users, 420 conversions (14.0%)
  • True effect: +4 pp absolute, +40% relative — a clear win
  • Sequential looks: 5 (currently at look 3, i.e. 60% information)
  • Multiple metrics: 3 (primary conversion + 2 secondary)
  • CUPED covariates: pre-experiment purchase history (high correlation ρ≈0.7)

Expected outcomes
-----------------
  • Hypothesis test: significant (p << 0.05), z > 4
  • Sequential: STOP_WIN (z >> OBF boundary at t=0.60 ≈ 2.53)
  • CUPED: variance reduced relative to unadjusted
  • BH correction (3 metrics): primary metric still rejected after correction
  • Overall recommendation: STOP_WIN

Consistency checks
------------------
  INTa  Sequential decision STOP_WIN → overall_recommendation must be STOP_WIN
  INTb  primary_result.is_significant → lift_abs > 0 (direction consistent)
  INTc  CUPED adjusted p-value ≤ unadjusted p-value (variance reduction helps)
  INTd  corrected_results present (n_metrics=3 triggers BH)
  INTe  warnings list is present (may be empty; must not be None)
  INTf  plain_english string is non-empty

Failure diagnosis
-----------------
• INTa fail: sequential decision not propagated to overall_recommendation.
• INTb fail: lift direction and significance sign mismatch.
• INTc fail: CUPED adjusted p is higher — variance reduction not achieved.
• INTd fail: corrections skipped despite n_metrics > 1.
"""

from __future__ import annotations

import numpy as np

from app.stats.engine import ExperimentConfig, ExperimentData, analyze_experiment
from tests.validation._report import record

_MODULE = "engine_integration"
_RNG_SEED = 42
_P_TOL = 0.001


def _build_cuped_covariates(
    n_ctrl: int,
    n_trt: int,
    ctrl_successes: int,
    trt_successes: int,
    seed: int,
) -> list[float]:
    """Build pre-experiment covariates correlated with conversion outcome.

    Converters (outcome=1) receive a higher pre-experiment score to simulate
    real-world pre-post correlation (ρ ≈ 0.4–0.7).
    """
    rng = np.random.default_rng(seed)
    # Control group: successes first, then failures
    ctrl_scores = np.concatenate(
        [
            rng.normal(0.6, 0.2, ctrl_successes),  # converters: higher scores
            rng.normal(0.3, 0.2, n_ctrl - ctrl_successes),  # non-converters
        ]
    )
    # Treatment group
    trt_scores = np.concatenate(
        [
            rng.normal(0.6, 0.2, trt_successes),
            rng.normal(0.3, 0.2, n_trt - trt_successes),
        ]
    )
    return list(np.clip(ctrl_scores, 0.0, 1.0)) + list(np.clip(trt_scores, 0.0, 1.0))


def _run_integration(
    scenario_label: str,
    config: ExperimentConfig,
    data: ExperimentData,
    current_look: int | None,
    expected_recommendation: str,
    notes: str = "",
) -> None:
    result = analyze_experiment(config, data, current_look=current_look)

    # ── INTa: sequential STOP_WIN → overall STOP_WIN ─────────────────────────
    seq_dec = result.sequential_status.decision if result.sequential_status else "N/A"
    inta_pass = (
        result.sequential_status is None
        or seq_dec != "STOP_WIN"
        or result.overall_recommendation == "STOP_WIN"
    )

    # ── INTb: significance direction consistent with lift ────────────────────
    intb_pass = (
        not result.primary_result.is_significant
        or result.primary_result.lift_abs != 0.0
    )

    # ── INTc: CUPED adjusted p ≤ unadjusted p (when CUPED ran) ──────────────
    if result.cuped_result is not None:
        adj_p = result.cuped_result.adjusted_test_result.p_value
        unadj_p = result.cuped_result.unadjusted_test_result.p_value
        intc_pass = adj_p <= unadj_p + _P_TOL  # allow tiny floating-point slack
        intc_note = f"adj_p={adj_p:.4f}, unadj_p={unadj_p:.4f}"
    else:
        intc_pass = True
        intc_note = "CUPED not run (no covariates)"

    # ── INTd: corrections present when n_metrics > 1 ─────────────────────────
    intd_pass = config.n_metrics <= 1 or result.corrected_results is not None

    # ── INTe/f: metadata present ──────────────────────────────────────────────
    inte_pass = result.warnings is not None
    intf_pass = bool(result.plain_english)

    # ── Recommendation check ─────────────────────────────────────────────────
    rec_pass = result.overall_recommendation == expected_recommendation

    all_pass = (
        inta_pass
        and intb_pass
        and intc_pass
        and intd_pass
        and inte_pass
        and intf_pass
        and rec_pass
    )

    failures: list[str] = []
    if not inta_pass:
        failures.append(
            f"INTa: seq={seq_dec} but rec={result.overall_recommendation} (should be STOP_WIN)"
        )
    if not intb_pass:
        failures.append("INTb: significant but lift_abs=0")
    if not intc_pass:
        failures.append(f"INTc: CUPED adj_p > unadj_p ({intc_note})")
    if not intd_pass:
        failures.append(
            f"INTd: n_metrics={config.n_metrics} but corrected_results=None"
        )
    if not inte_pass:
        failures.append("INTe: warnings is None")
    if not intf_pass:
        failures.append("INTf: plain_english is empty")
    if not rec_pass:
        failures.append(
            f"recommendation: expected {expected_recommendation}, got {result.overall_recommendation}"
        )

    likely = "; ".join(failures) if failures else ""

    record(
        module=_MODULE,
        scenario=scenario_label,
        expected=(
            f"rec={expected_recommendation}, sig={True}, "
            f"seq={seq_dec if result.sequential_status else 'N/A'}, "
            f"corrections={'present' if result.corrected_results else 'absent'}"
        ),
        observed=(
            f"rec={result.overall_recommendation}, "
            f"sig={result.primary_result.is_significant}, "
            f"seq={seq_dec}, "
            f"corrections={'present' if result.corrected_results else 'absent'}"
        ),
        delta=f"{len(failures)} consistency failure(s)",
        tolerance="0 consistency failures; exact recommendation match",
        passed=all_pass,
        likely_cause=likely,
        notes=notes,
    )

    assert all_pass, f"{scenario_label}: {'; '.join(failures)}"


def test_int1_clear_winner_sequential_stop() -> None:
    """INT1: Strong effect (40% relative lift) at look 3/5 → STOP_WIN.

    With z >> 2.53 (OBF boundary at t=0.60), the sequential test declares a
    winner before the planned final look.  The engine must propagate this to
    overall_recommendation = 'STOP_WIN'.
    """
    ctrl_n, ctrl_s = 3000, 300  # 10.0%
    trt_n, trt_s = 3000, 420  # 14.0%

    covariates = _build_cuped_covariates(ctrl_n, trt_n, ctrl_s, trt_s, seed=_RNG_SEED)

    config = ExperimentConfig(
        alpha=0.05,
        power=0.80,
        test_type="proportion",
        sequential_looks=5,
        n_metrics=3,
        has_cuped_data=True,
    )
    data = ExperimentData(
        control_n=ctrl_n,
        treatment_n=trt_n,
        control_success=ctrl_s,
        treatment_success=trt_s,
        cuped_covariates=covariates,
    )

    _run_integration(
        scenario_label="INT1: clear winner, +40% lift, look 3/5, CUPED+corrections",
        config=config,
        data=data,
        current_look=3,
        expected_recommendation="STOP_WIN",
        notes=(
            "Control=10%, Treatment=14%.  "
            "z >> OBF(t=0.60)≈2.53 → STOP_WIN.  "
            "CUPED should further reduce variance.  "
            "BH correction on 3 metrics; primary should still be significant."
        ),
    )


def test_int2_no_effect_underpowered() -> None:
    """INT2: No effect, underpowered sample → RUN (not enough data yet).

    Control=10%, treatment=10.5% — minimal difference.  Sample n=200 per group
    is far below the required ~8 000 per group for 5%→6% MDE.  The engine
    should recommend RUN (keep collecting data), not STOP.
    """
    config = ExperimentConfig(
        alpha=0.05,
        power=0.80,
        test_type="proportion",
        sequential_looks=1,  # fixed-horizon, no sequential adjustment
        n_metrics=1,
        has_cuped_data=False,
    )
    data = ExperimentData(
        control_n=200,
        treatment_n=200,
        control_success=20,  # 10.0%
        treatment_success=21,  # 10.5%
    )

    result = analyze_experiment(config, data)

    # Not significant, n below required → RUN
    passed = result.overall_recommendation == "RUN"
    likely = (
        (
            "Should be RUN: not significant (p >> 0.05) and current_n << required_n. "
            "Check that recommendation logic correctly identifies underpowered state."
        )
        if not passed
        else ""
    )

    record(
        module=_MODULE,
        scenario="INT2: no effect, underpowered (n=200 vs ~8000 required)",
        expected="RUN (not significant, underpowered)",
        observed=result.overall_recommendation,
        delta="exact match",
        tolerance="exact",
        passed=passed,
        likely_cause=likely,
        notes=f"p={result.primary_result.p_value:.3f}, warnings={result.warnings}",
    )

    assert passed, (
        f"INT2: expected RUN, got {result.overall_recommendation}. "
        f"p={result.primary_result.p_value:.3f}. {likely}"
    )


def test_int3_no_effect_fully_powered() -> None:
    """INT3: No effect, fully powered sample → NO_EFFECT.

    Control=10%, treatment=10.1%.  With planned_n_per_group=10 000, the
    experiment has collected its budget and found no significant effect.
    Recommendation: NO_EFFECT.
    """
    config = ExperimentConfig(
        alpha=0.05,
        power=0.80,
        test_type="proportion",
        sequential_looks=1,
        n_metrics=1,
        has_cuped_data=False,
        planned_n_per_group=10_000,
    )
    data = ExperimentData(
        control_n=10_000,
        treatment_n=10_000,
        control_success=1000,  # 10.0%
        treatment_success=1010,  # 10.1%
    )

    result = analyze_experiment(config, data)

    # p >> 0.05 and n >= planned → NO_EFFECT
    passed = result.overall_recommendation == "NO_EFFECT"
    likely = (
        (
            "Should be NO_EFFECT: not significant, n ≥ planned. "
            "Check that recommendation uses >= (not >) for the n comparison."
        )
        if not passed
        else ""
    )

    record(
        module=_MODULE,
        scenario="INT3: no effect, fully powered (n=10 000, planned=10 000)",
        expected="NO_EFFECT",
        observed=result.overall_recommendation,
        delta="exact match",
        tolerance="exact",
        passed=passed,
        likely_cause=likely,
        notes=f"p={result.primary_result.p_value:.3f}",
    )

    assert passed, (
        f"INT3: expected NO_EFFECT, got {result.overall_recommendation}. "
        f"p={result.primary_result.p_value:.3f}. {likely}"
    )
