"""Bayesian analysis for A/B experiment results.

Proportion experiments: Beta-Binomial conjugate with uninformative Beta(1,1) prior.
Mean experiments: Normal-CLT approximation (Normal posterior via observed mean and SE).

Both functions return P(treatment > control) and a 95% credible interval for the
lift via Monte Carlo sampling.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel


class BayesianResult(BaseModel):
    """Result of a Bayesian analysis run."""

    prob_treatment_better: float
    prob_control_better: float
    expected_lift: float
    credible_interval_low: float
    credible_interval_high: float
    method: str
    interpretation: str
    n_samples: int


def _interpret(prob_treatment_better: float, prob_control_better: float) -> str:
    if prob_treatment_better > 0.95:
        return f"Strong evidence that treatment is better (P={prob_treatment_better:.1%})."
    if prob_treatment_better > 0.80:
        return f"Moderate evidence that treatment is better (P={prob_treatment_better:.1%})."
    if prob_control_better > 0.95:
        return f"Strong evidence that control is better (P={prob_control_better:.1%})."
    return f"Inconclusive — treatment advantage probability {prob_treatment_better:.1%}."


def run_bayesian_proportion(
    n_control: int,
    success_control: int,
    n_treatment: int,
    success_treatment: int,
    n_samples: int = 50_000,
    rng: np.random.Generator | None = None,
) -> BayesianResult:
    """Beta-Binomial Bayesian analysis for a proportion experiment.

    Args:
        n_control: Subjects in the control group.
        success_control: Successes in the control group.
        n_treatment: Subjects in the treatment group.
        success_treatment: Successes in the treatment group.
        n_samples: Monte Carlo sample count.
        rng: Optional Generator for reproducibility.

    Returns:
        BayesianResult with posterior probabilities and lift estimates.
    """
    if rng is None:
        rng = np.random.default_rng(42)

    samples_ctrl = rng.beta(1 + success_control, 1 + (n_control - success_control), size=n_samples)
    samples_trt = rng.beta(1 + success_treatment, 1 + (n_treatment - success_treatment), size=n_samples)
    diff = samples_trt - samples_ctrl

    p_trt = float(np.mean(diff > 0))
    p_ctrl = float(np.mean(diff < 0))

    return BayesianResult(
        prob_treatment_better=p_trt,
        prob_control_better=p_ctrl,
        expected_lift=float(np.mean(diff)),
        credible_interval_low=float(np.percentile(diff, 2.5)),
        credible_interval_high=float(np.percentile(diff, 97.5)),
        method="Beta-Binomial (uninformative Beta(1,1) prior)",
        interpretation=_interpret(p_trt, p_ctrl),
        n_samples=n_samples,
    )


def run_bayesian_mean(
    control_values: list[float],
    treatment_values: list[float],
    n_samples: int = 50_000,
    rng: np.random.Generator | None = None,
) -> BayesianResult:
    """Normal-CLT Bayesian analysis for a mean experiment.

    Approximates each group's posterior as Normal(observed_mean, observed_SE^2),
    then draws Monte Carlo samples to estimate P(treatment > control) and the
    95% credible interval for the mean lift.

    Args:
        control_values: Per-subject outcomes in the control group.
        treatment_values: Per-subject outcomes in the treatment group.
        n_samples: Monte Carlo sample count.
        rng: Optional Generator for reproducibility.

    Returns:
        BayesianResult with posterior probabilities and lift estimates.
    """
    if rng is None:
        rng = np.random.default_rng(42)

    ctrl = np.array(control_values, dtype=float)
    trt = np.array(treatment_values, dtype=float)

    ctrl_se = max(float(np.std(ctrl, ddof=1) / np.sqrt(len(ctrl))), 1e-10)
    trt_se = max(float(np.std(trt, ddof=1) / np.sqrt(len(trt))), 1e-10)

    samples_ctrl = rng.normal(float(np.mean(ctrl)), ctrl_se, size=n_samples)
    samples_trt = rng.normal(float(np.mean(trt)), trt_se, size=n_samples)
    diff = samples_trt - samples_ctrl

    p_trt = float(np.mean(diff > 0))
    p_ctrl = float(np.mean(diff < 0))

    return BayesianResult(
        prob_treatment_better=p_trt,
        prob_control_better=p_ctrl,
        expected_lift=float(np.mean(diff)),
        credible_interval_low=float(np.percentile(diff, 2.5)),
        credible_interval_high=float(np.percentile(diff, 97.5)),
        method="Normal-CLT approximation",
        interpretation=_interpret(p_trt, p_ctrl),
        n_samples=n_samples,
    )
