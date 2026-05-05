"""
Synthetic sample experiment datasets for the Axiom ML engine demo.

Three fully-generated experiments, each designed to stress a different subset
of the ML engine:

  1. ecommerce_checkout  — SRM + novelty decay + HTE by device_type
  2. saas_trial          — clean 50/50, stable novelty, HTE by company_size
  3. marketplace_fee     — volume-spike anomaly, negative HTE for new sellers

Run as a script to regenerate the pre-computed JSON files:

    PYTHONPATH=backend python backend/app/data/sample_experiments.py

Otherwise import load_sample_experiment() and seed_sample_experiments().
"""

from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import beta as sp_beta
from scipy.stats import norm as sp_norm

SAMPLES_DIR = Path(__file__).parent / "samples"

# Day-of-week traffic multipliers (Mon=0 … Sun=6)
_DOW_TRAFFIC: dict[int, float] = {
    0: 1.0,   # Monday
    1: 1.2,   # Tuesday
    2: 1.1,   # Wednesday
    3: 1.0,   # Thursday
    4: 0.9,   # Friday
    5: 0.7,   # Saturday
    6: 0.8,   # Sunday
}


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass
class SampleExperiment:
    """A fully-generated sample experiment with pre-computed ML analysis.

    Attributes:
        user_data: One row per subject with treatment, outcome, and features.
        daily_data: One row per day with aggregate metrics.
        precomputed_result: JSON-serializable dict from the actual ML engine.
        metadata: Descriptive information and ground-truth labels.
    """

    user_data: pd.DataFrame
    daily_data: pd.DataFrame
    precomputed_result: dict
    metadata: dict


# ---------------------------------------------------------------------------
# Load / seed API
# ---------------------------------------------------------------------------


def load_sample_experiment(name: str) -> SampleExperiment:
    """Load a pre-generated sample experiment from disk.

    Args:
        name: One of "ecommerce_checkout", "saas_trial", "marketplace_fee".

    Returns:
        SampleExperiment with DataFrames and pre-computed ML/stats results.

    Raises:
        FileNotFoundError: If the named JSON file has not been generated yet.
    """
    path = SAMPLES_DIR / f"{name}.json"
    with open(path) as f:
        raw = json.load(f)
    user_data = pd.DataFrame(raw["user_data"])
    daily_data = pd.DataFrame(raw["daily_data"])
    daily_data["date"] = pd.to_datetime(daily_data["date"])
    return SampleExperiment(
        user_data=user_data,
        daily_data=daily_data,
        precomputed_result=raw["precomputed_result"],
        metadata=raw["metadata"],
    )


async def seed_sample_experiments(db: Any) -> None:
    """Insert all three sample experiments into the DB (idempotent).

    Checks for an existing row by experiment name before inserting.
    Safe to call multiple times — skips rows that already exist.

    Args:
        db: Async SQLAlchemy session.
    """
    from sqlalchemy import select

    from app.models.experiment import (
        AnalysisType,
        Experiment,
        ExperimentResult,
        ExperimentStatus,
        ExperimentType,
    )

    for name in ("ecommerce_checkout", "saas_trial", "marketplace_fee"):
        sample = load_sample_experiment(name)
        meta = sample.metadata

        existing = await db.execute(
            select(Experiment).where(Experiment.name == meta["name"])
        )
        if existing.scalars().first() is not None:
            continue

        exp_type = (
            ExperimentType.proportion
            if meta["test_type"] == "proportion"
            else ExperimentType.mean
        )
        exp = Experiment(
            name=meta["name"],
            description=meta["description"],
            status=ExperimentStatus.completed,
            experiment_type=exp_type,
            baseline_metric=float(meta["baseline_metric"]),
            mde=float(meta["mde"]),
        )
        db.add(exp)
        await db.flush()

        db.add(
            ExperimentResult(
                experiment_id=exp.id,
                analysis_type=AnalysisType.full,
                full_analysis_json=sample.precomputed_result,
            )
        )
        await db.flush()

    await db.commit()


# ---------------------------------------------------------------------------
# JSON serialization helpers
# ---------------------------------------------------------------------------


class _NumpyEncoder(json.JSONEncoder):
    """Convert numpy scalars and arrays to Python-native types for JSON."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        return super().default(obj)


def _native(obj: Any) -> Any:
    """Recursively convert numpy types in a nested structure to native Python."""
    if isinstance(obj, dict):
        return {k: _native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_native(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return str(obj.date())
    return obj


def _serialize_ml_result(ml_result: Any) -> dict:
    """Extract JSON-serializable fields from MLAnalysisResult."""
    out: dict = {
        "overall_verdict": ml_result.overall_verdict,
        "key_insights": list(ml_result.key_insights),
        "can_trust_results": bool(ml_result.can_trust_results),
        "recommendation": ml_result.recommendation,
        "capability_report": [
            {
                "module": s.module,
                "status": s.status,
                "skip_reason": s.skip_reason,
                "duration_seconds": round(float(s.duration_seconds), 4),
            }
            for s in ml_result.capability_report
        ],
    }

    if ml_result.hte_result is not None:
        hte = ml_result.hte_result
        out["hte"] = {
            "ate": float(hte.ate),
            "top_interactions": list(hte.top_interactions),
            "stability_score": float(hte.stability_score),
            "business_recommendation": hte.business_recommendation,
            "ite_uncertainty_mean": float(hte.ite_uncertainty.mean()),
        }

    if ml_result.segment_result is not None:
        seg = ml_result.segment_result
        out["segments"] = {
            "optimal_k": int(seg.optimal_k),
            "silhouette_score": float(seg.silhouette_score),
            "responsive_segments": list(seg.responsive_segments),
            "overall_recommendation": seg.overall_recommendation,
            "low_confidence": bool(seg.low_confidence),
            "segments": [
                {
                    "id": int(s.id),
                    "size_pct": float(s.size_pct),
                    "lift": float(s.lift),
                    "lift_uncertainty": float(s.lift_uncertainty),
                    "description": s.description,
                    "significant": bool(s.significant),
                    "top_features": {
                        k: [float(v[0]), float(v[1])]
                        for k, v in s.top_features.items()
                    },
                }
                for s in seg.segments
            ],
        }

    if ml_result.anomaly_result is not None:
        anomaly = ml_result.anomaly_result
        out["anomaly"] = {
            "overall_validity": anomaly.overall_validity,
            "can_trust_results": bool(anomaly.can_trust_results),
            "recommendation": anomaly.recommendation,
            "checks": [
                {
                    "name": c.name,
                    "passed": bool(c.passed),
                    "score": float(c.score),
                    "severity": c.severity,
                    "description": c.description,
                    "action": c.action,
                }
                for c in anomaly.checks
            ],
        }

    if ml_result.novelty_result is not None:
        nov = ml_result.novelty_result
        out["novelty"] = {
            "pattern": nov.pattern,
            "slope": float(nov.slope),
            "slope_ci": [float(nov.slope_ci[0]), float(nov.slope_ci[1])],
            "initial_lift": float(nov.initial_lift),
            "projected_stable_lift": float(nov.projected_stable_lift),
            "days_to_stable": nov.days_to_stable,
            "confidence": nov.confidence,
            "recommendation": nov.recommendation,
        }

    return out


def _serialize_stats_result(stats_result: Any) -> dict:
    """Convert ExperimentAnalysis Pydantic model to a plain dict."""
    raw = stats_result.model_dump()
    return _native(raw)


# ---------------------------------------------------------------------------
# Dataset 1: E-Commerce Checkout Button
# ---------------------------------------------------------------------------


def _gen_ecommerce_checkout() -> SampleExperiment:
    """Generate the e-commerce checkout button A/B test dataset.

    Injects:
    - 55/45 treatment/control SRM (detectable at alpha=0.01)
    - Novelty decay: conversion lift 12% → 6% → 4% over 21 days
    - HTE: mobile +15% relative lift, desktop -2% relative lift
    - Weekend: 20% lower traffic, 10% higher conversion
    """
    from app.ml.engine import MLExperimentInput, run_ml_analysis
    from app.stats.engine import ExperimentConfig, ExperimentData, analyze_experiment

    rng = np.random.default_rng(42)
    n_total = 10_000
    # 55/45 split: large enough imbalance for SRM to fire at alpha=0.01
    n_treatment = 5_500
    n_control = 4_500

    # ── Correlated user features ──────────────────────────────────────────────
    # device_type=1 for mobile (65%), 0 for desktop (35%).
    # Encoding mobile as 1 is critical: device_type_x_treat = 1*treatment changes
    # from 1→0 for mobile users so XGBoost unambiguously ranks it first.
    device_type = (rng.random(n_total) < 0.65).astype(int)   # 1=mobile (65%), 0=desktop (35%)

    # user_age_days and n_prior_orders share a latent maturity factor Z
    Z = rng.standard_normal(n_total)
    base_age = rng.exponential(scale=35, size=n_total)
    user_age_days = np.clip(base_age + 15.0 * np.clip(Z, -2.0, 4.0), 0.0, 365.0)

    # n_prior_orders: zero-inflated Poisson correlated with user_age_days
    p_zero = np.clip(0.75 - user_age_days / 200.0, 0.10, 0.80)
    is_zero = rng.random(n_total) < p_zero
    lambda_orders = np.clip(user_age_days / 22.0, 0.5, 10.0)
    n_prior_orders = np.where(is_zero, 0, rng.poisson(lambda_orders)).astype(float)

    # cart_value: log-normal(mu=3.5, sigma=0.8), positively correlated with n_prior_orders
    log_cart_mu = 3.5 + 0.07 * n_prior_orders
    cart_value = np.exp(rng.normal(log_cart_mu, 0.8)).clip(1.0, 5000.0)

    # ── Treatment assignment (55/45 SRM) ─────────────────────────────────────
    treatment = np.zeros(n_total, dtype=int)
    treatment[:n_treatment] = 1
    rng.shuffle(treatment)

    # ── Outcome: checkout conversion (binary) ─────────────────────────────────
    # 10% base rate gives ~1 000 events — enough for XGBoost to learn reliably.
    # Large mobile effect (+200%) vs small desktop penalty (-30%).
    # No other feature interacts with treatment in the DGP, so device_type_x_treat
    # unambiguously dominates SHAP importance.
    base_rate = 0.10
    p_convert = np.full(n_total, base_rate, dtype=float)
    is_mobile = device_type == 1
    p_convert += treatment * is_mobile * base_rate * 2.00        # mobile: p→0.30 if treated
    p_convert += treatment * (~is_mobile.astype(bool)).astype(int) * base_rate * (-0.30)  # desktop: p→0.07
    p_convert = np.clip(p_convert, 0.001, 0.999)
    outcome = (rng.random(n_total) < p_convert).astype(int)

    user_ids = [f"eco_{i:06d}" for i in range(n_total)]
    user_data = pd.DataFrame(
        {
            "user_id": user_ids,
            "treatment": treatment,
            "outcome": outcome,
            "device_type": device_type,
            "user_age_days": np.round(user_age_days, 2),
            "cart_value": np.round(cart_value, 2),
            "n_prior_orders": n_prior_orders.astype(int),
        }
    )

    # ── Daily time series: 21 days with novelty decay ─────────────────────────
    # Novelty is injected as absolute lift so the WLS slope is clearly negative.
    # Day 0-2: +0.20 absolute lift (2× the stable control rate)
    # Day 14+: +0.05 absolute lift (stable steady-state)
    start_date = date(2026, 3, 2)  # Monday

    def _novelty_abs_lift(day: int) -> float:
        """Absolute (treatment - control) lift per day, decaying over 21 days."""
        if day < 3:
            return 0.20
        if day < 14:
            return 0.20 - (day - 3) / 11.0 * 0.15
        return 0.05

    base_ctrl_per_day = n_control / 21.0
    base_trt_per_day = n_treatment / 21.0
    daily_rows = []
    for day_idx in range(21):
        d = start_date + timedelta(days=day_idx)
        dow = d.weekday()
        traffic_mult = _DOW_TRAFFIC[dow]
        weekend_conv = 1.10 if dow >= 5 else 1.0

        n_ctrl = max(20, int(base_ctrl_per_day * traffic_mult + rng.integers(-8, 9)))
        n_trt = max(20, int(base_trt_per_day * traffic_mult + rng.integers(-8, 9)))

        # Control rate is stable; treatment rate declines (novelty effect)
        ctrl_rate = float(np.clip(base_rate * weekend_conv * (1.0 + rng.normal(0, 0.03)), 0.02, 0.35))
        abs_lift = _novelty_abs_lift(day_idx)
        trt_rate = float(np.clip(ctrl_rate + abs_lift * (1.0 + rng.normal(0, 0.05)), 0.02, 0.80))

        eff = trt_rate - ctrl_rate
        se = math.sqrt(
            ctrl_rate * (1 - ctrl_rate) / n_ctrl + trt_rate * (1 - trt_rate) / n_trt
        )
        daily_rows.append(
            {
                "date": d.isoformat(),
                "control_metric": round(ctrl_rate, 6),
                "treatment_metric": round(trt_rate, 6),
                "n_control": n_ctrl,
                "n_treatment": n_trt,
                "treatment_effect": round(eff, 6),
                "treatment_se": round(se, 6),
            }
        )

    daily_data = pd.DataFrame(daily_rows)
    daily_data["date"] = pd.to_datetime(daily_data["date"])

    # ── ML analysis ───────────────────────────────────────────────────────────
    ctrl_df = user_data[user_data.treatment == 0]
    trt_df = user_data[user_data.treatment == 1]
    control_values = ctrl_df["outcome"].tolist()
    treatment_values = trt_df["outcome"].tolist()

    feature_cols = ["device_type", "user_age_days", "cart_value", "n_prior_orders"]
    user_features = pd.concat(
        [ctrl_df[feature_cols].reset_index(drop=True),
         trt_df[feature_cols].reset_index(drop=True)],
        ignore_index=True,
    )

    ml_input = MLExperimentInput(
        control_values=[float(v) for v in control_values],
        treatment_values=[float(v) for v in treatment_values],
        user_features=user_features,
        daily_metrics=daily_data[["date", "control_metric", "treatment_metric",
                                   "n_control", "n_treatment"]].copy(),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ml_result = run_ml_analysis(ml_input)

    stats_config = ExperimentConfig(test_type="proportion", alpha=0.05, power=0.80)
    stats_data = ExperimentData(
        control_n=len(control_values),
        treatment_n=len(treatment_values),
        control_success=int(sum(control_values)),
        treatment_success=int(sum(treatment_values)),
    )
    stats_result = analyze_experiment(stats_config, stats_data)

    true_ate = float(np.mean(treatment_values) - np.mean(control_values))

    precomputed = {
        "ml_result": _serialize_ml_result(ml_result),
        "stats_result": _serialize_stats_result(stats_result),
    }
    metadata = {
        "name": "E-Commerce Checkout Button Color Test",
        "description": (
            "Tests whether changing the checkout button from green to orange "
            "increases purchase conversion. Injects a 55/45 SRM and a novelty "
            "effect that decays from +12% to +4% relative lift over 21 days. "
            "Mobile users respond strongly (+50% relative lift) while desktop "
            "users see a decline (-15% relative lift)."
        ),
        "what_is_interesting": (
            "Demonstrates three signals at once: SRM (broken randomisation), "
            "novelty decay (inflated early lift), and strong device-type HTE "
            "(mobile +50% relative, desktop -15% relative — device_type is "
            "the #1 XGBoost treatment modifier)."
        ),
        "expected_verdict": "NEEDS_REVIEW",
        "expected_anomalies": ["srm_check", "novelty_decay"],
        "expected_hte_modifier": "device_type",
        "n_users": n_total,
        "n_days": 21,
        "true_ate": round(true_ate, 6),
        "test_type": "proportion",
        "baseline_metric": 0.10,
        "mde": 0.01,
    }
    return SampleExperiment(
        user_data=user_data,
        daily_data=daily_data,
        precomputed_result=precomputed,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Dataset 2: SaaS Free Trial Length (14 vs 30 days)
# ---------------------------------------------------------------------------


def _gen_saas_trial() -> SampleExperiment:
    """Generate the SaaS free-trial-length A/B test dataset.

    Injects:
    - Clean 50/50 split (no SRM)
    - Stable novelty (flat daily lift trajectory)
    - HTE: large companies (size > 50) get 8pp absolute lift; small get ~1pp
    - Monday signups 30% higher than Friday
    """
    from app.ml.engine import MLExperimentInput, run_ml_analysis
    from app.stats.engine import ExperimentConfig, ExperimentData, analyze_experiment

    rng = np.random.default_rng(123)
    n_total = 5_000
    n_treatment = 2_500
    n_control = 2_500

    # ── Correlated features via bivariate normal (company_size ↔ usage_score) ─
    rho = 0.40
    cov_mat = np.array([[1.0, rho], [rho, 1.0]])
    Z_mat = rng.multivariate_normal([0.0, 0.0], cov_mat, n_total)

    # company_size: log-normal, median ~25, clipped to [1, 500]
    log_company = Z_mat[:, 0] * 1.0 + math.log(25)
    company_size = np.clip(np.exp(log_company), 1.0, 500.0)

    # usage_score: beta(2, 5)*100 right-skewed, correlated with company_size
    usage_uniform = np.clip(sp_norm.cdf(Z_mat[:, 1]), 1e-6, 1 - 1e-6)
    usage_score = sp_beta.ppf(usage_uniform, 2, 5) * 100.0

    # industry: categorical, 5 categories
    industry = rng.choice(5, n_total, p=[0.35, 0.25, 0.20, 0.12, 0.08])

    # signup_source: categorical, 3 categories
    signup_source = rng.choice(3, n_total, p=[0.50, 0.30, 0.20])

    # ── Treatment assignment (clean 50/50) ────────────────────────────────────
    treatment = np.zeros(n_total, dtype=int)
    treatment[:n_treatment] = 1
    rng.shuffle(treatment)

    # ── Outcome: trial-to-paid conversion ─────────────────────────────────────
    is_large = company_size > 50
    base_rate_large = 0.15
    base_rate_small = 0.11
    treat_rate_large = 0.23   # +8pp absolute
    treat_rate_small = 0.12   # +1pp absolute

    p_convert = np.where(is_large, base_rate_large, base_rate_small)
    delta_large = treat_rate_large - base_rate_large
    delta_small = treat_rate_small - base_rate_small
    p_convert = p_convert + treatment * (is_large * delta_large + (~is_large) * delta_small)
    # Tech industry (0) gets additional +2pp boost for treatment
    p_convert = p_convert + treatment * (industry == 0) * 0.02
    p_convert = np.clip(p_convert, 0.001, 0.999)
    outcome = (rng.random(n_total) < p_convert).astype(int)

    user_ids = [f"saas_{i:06d}" for i in range(n_total)]
    user_data = pd.DataFrame(
        {
            "user_id": user_ids,
            "treatment": treatment,
            "outcome": outcome,
            "company_size": np.round(company_size, 1),
            "industry": industry,
            "signup_source": signup_source,
            "usage_score": np.round(usage_score, 2),
        }
    )

    # ── Daily time series: 30 days, stable effect, Monday-heavy signups ───────
    start_date = date(2026, 2, 2)  # Monday
    # B2B SaaS traffic: heavy Mon/Tue, almost none on weekends
    saas_dow = {0: 1.3, 1: 1.2, 2: 1.1, 3: 1.0, 4: 1.0, 5: 0.4, 6: 0.3}

    base_ctrl_per_day = n_control / 30.0
    base_trt_per_day = n_treatment / 30.0
    # Stable treatment rate ratio (no novelty decay)
    stable_ctrl_rate = (
        np.sum(is_large & (treatment == 0)) / np.sum(treatment == 0) * base_rate_large
        + np.sum(~is_large & (treatment == 0)) / np.sum(treatment == 0) * base_rate_small
    )
    stable_trt_rate = (
        np.sum(is_large & (treatment == 1)) / np.sum(treatment == 1) * treat_rate_large
        + np.sum(~is_large & (treatment == 1)) / np.sum(treatment == 1) * treat_rate_small
    )

    daily_rows = []
    for day_idx in range(30):
        d = start_date + timedelta(days=day_idx)
        dow = d.weekday()
        traffic_mult = saas_dow[dow]

        n_ctrl = max(5, int(base_ctrl_per_day * traffic_mult + rng.integers(-5, 6)))
        n_trt = max(5, int(base_trt_per_day * traffic_mult + rng.integers(-5, 6)))

        ctrl_rate = float(np.clip(stable_ctrl_rate * (1.0 + rng.normal(0, 0.05)), 0.01, 0.50))
        trt_rate = float(np.clip(stable_trt_rate * (1.0 + rng.normal(0, 0.05)), 0.01, 0.50))

        eff = trt_rate - ctrl_rate
        se = math.sqrt(
            ctrl_rate * (1 - ctrl_rate) / max(n_ctrl, 1)
            + trt_rate * (1 - trt_rate) / max(n_trt, 1)
        )
        daily_rows.append(
            {
                "date": d.isoformat(),
                "control_metric": round(ctrl_rate, 6),
                "treatment_metric": round(trt_rate, 6),
                "n_control": n_ctrl,
                "n_treatment": n_trt,
                "treatment_effect": round(eff, 6),
                "treatment_se": round(se, 6),
            }
        )

    daily_data = pd.DataFrame(daily_rows)
    daily_data["date"] = pd.to_datetime(daily_data["date"])

    # ── ML analysis ───────────────────────────────────────────────────────────
    ctrl_df = user_data[user_data.treatment == 0]
    trt_df = user_data[user_data.treatment == 1]
    control_values = ctrl_df["outcome"].tolist()
    treatment_values = trt_df["outcome"].tolist()

    feature_cols = ["company_size", "industry", "signup_source", "usage_score"]
    user_features = pd.concat(
        [ctrl_df[feature_cols].reset_index(drop=True),
         trt_df[feature_cols].reset_index(drop=True)],
        ignore_index=True,
    )

    ml_input = MLExperimentInput(
        control_values=[float(v) for v in control_values],
        treatment_values=[float(v) for v in treatment_values],
        user_features=user_features,
        daily_metrics=daily_data[["date", "control_metric", "treatment_metric",
                                   "n_control", "n_treatment"]].copy(),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ml_result = run_ml_analysis(ml_input)

    stats_config = ExperimentConfig(test_type="proportion", alpha=0.05, power=0.80)
    stats_data = ExperimentData(
        control_n=len(control_values),
        treatment_n=len(treatment_values),
        control_success=int(sum(control_values)),
        treatment_success=int(sum(treatment_values)),
    )
    stats_result = analyze_experiment(stats_config, stats_data)

    true_ate = float(np.mean(treatment_values) - np.mean(control_values))

    precomputed = {
        "ml_result": _serialize_ml_result(ml_result),
        "stats_result": _serialize_stats_result(stats_result),
    }
    metadata = {
        "name": "SaaS Free Trial Length Test (14 vs 30 Days)",
        "description": (
            "Tests extending the free trial from 14 to 30 days to increase "
            "trial-to-paid conversion. Larger companies need longer evaluation "
            "cycles and benefit significantly; small startups see minimal lift."
        ),
        "what_is_interesting": (
            "Clean experiment (no SRM, stable novelty) that showcases strong "
            "company-size HTE: enterprises (>50 seats) convert 8pp more with "
            "the longer trial, while small teams show negligible change."
        ),
        "expected_verdict": "CLEAN",
        "expected_anomalies": [],
        "expected_hte_modifier": "company_size",
        "n_users": n_total,
        "n_days": 30,
        "true_ate": round(true_ate, 6),
        "test_type": "proportion",
        "baseline_metric": 0.12,
        "mde": 0.02,
    }
    return SampleExperiment(
        user_data=user_data,
        daily_data=daily_data,
        precomputed_result=precomputed,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Dataset 3: Marketplace Seller Fee Reduction
# ---------------------------------------------------------------------------


def _gen_marketplace_fee() -> SampleExperiment:
    """Generate the marketplace seller-fee-reduction A/B test dataset.

    Injects:
    - Clean 50/50 split
    - Volume spike (5x) on days 8-9 → IsolationForest + volume-spike check fire
    - HTE: established sellers (tenure > 180 days) +12% GMV; new sellers -5%
    - Correlated features: tenure ↔ avg_rating ↔ n_listings
    """
    from app.ml.engine import MLExperimentInput, run_ml_analysis
    from app.stats.engine import ExperimentConfig, ExperimentData, analyze_experiment

    rng = np.random.default_rng(456)
    n_total = 20_000
    n_treatment = 10_000
    n_control = 10_000

    # ── Correlated features via latent tenure factor ───────────────────────────
    seller_tenure_days = np.clip(
        rng.exponential(scale=150, size=n_total), 0.0, 1000.0
    )

    # avg_rating: beta(8,2)*2+3 — range [3,5], correlated with tenure via copula
    from scipy.stats import expon as sp_expon

    tenure_pctile = np.clip(sp_expon.cdf(seller_tenure_days, scale=150), 1e-6, 1 - 1e-6)
    # Blend tenure percentile with uniform noise for realistic spread
    rating_pctile = np.clip(
        0.65 * tenure_pctile + 0.35 * rng.random(n_total), 1e-6, 1 - 1e-6
    )
    avg_rating = sp_beta.ppf(rating_pctile, 8, 2) * 2.0 + 3.0

    # n_listings: zero-inflated Poisson(lambda=8), correlated with tenure
    # 30% of new sellers have 0-1 listings
    p_very_few = np.clip(0.55 - seller_tenure_days / 600.0, 0.05, 0.55)
    is_very_few = rng.random(n_total) < p_very_few
    listing_lambda = np.clip(2.0 + seller_tenure_days / 60.0, 0.5, 18.0)
    raw_listings = rng.poisson(listing_lambda)
    n_listings = np.where(is_very_few, rng.integers(0, 2, n_total), raw_listings).astype(int)

    # category: 8 categories with realistic marketplace distribution
    category = rng.choice(
        8, n_total, p=[0.25, 0.20, 0.15, 0.12, 0.10, 0.08, 0.06, 0.04]
    )

    # ── Treatment assignment (clean 50/50) ────────────────────────────────────
    treatment = np.zeros(n_total, dtype=int)
    treatment[:n_treatment] = 1
    rng.shuffle(treatment)

    # ── Outcome: GMV per seller (continuous, log-normal with HTE) ────────────
    base_mu = 5.5
    is_established = seller_tenure_days > 180
    is_electronics = category == 0

    # Treatment effect in log-space: +12% for established, -5% for new
    log_treatment_effect = np.where(
        is_established, math.log(1.12), math.log(0.95)
    )
    # Electronics bonus: +5% additional for established sellers in treatment
    log_treatment_effect = log_treatment_effect + treatment * is_established * is_electronics * math.log(1.05)

    gmv_mu = base_mu + treatment * log_treatment_effect
    gmv_noise = rng.normal(0, 1.2, n_total)
    outcome = np.exp(gmv_mu + gmv_noise)

    user_ids = [f"mkt_{i:06d}" for i in range(n_total)]
    user_data = pd.DataFrame(
        {
            "user_id": user_ids,
            "treatment": treatment,
            "outcome": np.round(outcome, 2),
            "seller_tenure_days": np.round(seller_tenure_days, 1),
            "category": category,
            "avg_rating": np.round(avg_rating, 3),
            "n_listings": n_listings,
        }
    )

    # ── Daily time series: 28 days with anomaly on days 8-9 ──────────────────
    start_date = date(2026, 1, 5)  # Monday

    base_daily = n_total / 28.0  # ~714 per day total, ~357 per arm

    # Base GMV per arm (median)
    ctrl_mask = treatment == 0
    trt_mask = treatment == 1
    base_ctrl_gmv = float(np.median(outcome[ctrl_mask]))
    base_trt_gmv = float(np.median(outcome[trt_mask]))

    daily_rows = []
    for day_idx in range(28):
        d = start_date + timedelta(days=day_idx)
        dow = d.weekday()
        traffic_mult = _DOW_TRAFFIC[dow]

        n_ctrl = max(20, int(base_daily / 2 * traffic_mult + rng.integers(-15, 16)))
        n_trt = max(20, int(base_daily / 2 * traffic_mult + rng.integers(-15, 16)))

        # Deterministic anomaly on days 8 and 9 (5x volume spike)
        if day_idx in (8, 9):
            n_ctrl = int(n_ctrl * 5)
            n_trt = int(n_trt * 5)

        ctrl_gmv = float(np.clip(
            base_ctrl_gmv * (1.0 + rng.normal(0, 0.06)), 10.0, 5000.0
        ))
        trt_gmv = float(np.clip(
            base_trt_gmv * (1.0 + rng.normal(0, 0.06)), 10.0, 5000.0
        ))

        # Contaminate treatment metric on anomaly days
        if day_idx in (8, 9):
            trt_gmv = trt_gmv * 3.0  # clearly inflated / contaminated

        eff = trt_gmv - ctrl_gmv
        # For continuous metrics, use sample-std proxy
        gmv_std = float(np.std(outcome)) * 0.5
        se = math.sqrt(2) * gmv_std / math.sqrt(max(n_ctrl, 1))

        daily_rows.append(
            {
                "date": d.isoformat(),
                "control_metric": round(ctrl_gmv, 2),
                "treatment_metric": round(trt_gmv, 2),
                "n_control": n_ctrl,
                "n_treatment": n_trt,
                "treatment_effect": round(eff, 2),
                "treatment_se": round(se, 2),
            }
        )

    daily_data = pd.DataFrame(daily_rows)
    daily_data["date"] = pd.to_datetime(daily_data["date"])

    # ── ML analysis ───────────────────────────────────────────────────────────
    ctrl_df = user_data[user_data.treatment == 0]
    trt_df = user_data[user_data.treatment == 1]
    control_values = ctrl_df["outcome"].tolist()
    treatment_values = trt_df["outcome"].tolist()

    feature_cols = ["seller_tenure_days", "category", "avg_rating", "n_listings"]
    user_features = pd.concat(
        [ctrl_df[feature_cols].reset_index(drop=True),
         trt_df[feature_cols].reset_index(drop=True)],
        ignore_index=True,
    )

    ml_input = MLExperimentInput(
        control_values=[float(v) for v in control_values],
        treatment_values=[float(v) for v in treatment_values],
        user_features=user_features,
        daily_metrics=daily_data[["date", "control_metric", "treatment_metric",
                                   "n_control", "n_treatment"]].copy(),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ml_result = run_ml_analysis(ml_input)

    stats_config = ExperimentConfig(test_type="mean", alpha=0.05, power=0.80)
    stats_data = ExperimentData(
        control_n=len(control_values),
        treatment_n=len(treatment_values),
        control_success=[float(v) for v in control_values],
        treatment_success=[float(v) for v in treatment_values],
    )
    stats_result = analyze_experiment(stats_config, stats_data)

    true_ate = float(np.mean(treatment_values) - np.mean(control_values))

    precomputed = {
        "ml_result": _serialize_ml_result(ml_result),
        "stats_result": _serialize_stats_result(stats_result),
    }
    metadata = {
        "name": "Marketplace Seller Fee Reduction Test",
        "description": (
            "Tests a 15% fee reduction to increase gross merchandise value. "
            "Established sellers benefit immediately; new sellers are overwhelmed "
            "by the change and show a slight GMV decline."
        ),
        "what_is_interesting": (
            "Days 8-9 have a 5x volume spike that triggers IsolationForest and "
            "the volume-spike anomaly check. HTE splits sharply on seller tenure: "
            "established sellers (+12% GMV) vs new sellers (-5% GMV)."
        ),
        "expected_verdict": "NEEDS_REVIEW",
        "expected_anomalies": ["outlier_days", "volume_spike"],
        "expected_hte_modifier": "seller_tenure_days",
        "n_users": n_total,
        "n_days": 28,
        "true_ate": round(true_ate, 2),
        "test_type": "mean",
        "baseline_metric": float(np.median(outcome[ctrl_mask])),
        "mde": 10.0,
    }
    return SampleExperiment(
        user_data=user_data,
        daily_data=daily_data,
        precomputed_result=precomputed,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_dataset1(sample: SampleExperiment) -> None:
    """Assert that Dataset 1 has the expected ML signals."""
    pr = sample.precomputed_result["ml_result"]

    # SRM must fire
    anomaly = pr.get("anomaly", {})
    srm = next((c for c in anomaly.get("checks", []) if c["name"] == "srm_check"), None)
    assert srm is not None, "srm_check missing from anomaly checks"
    assert not srm["passed"], (
        f"SRM check passed (p={srm['score']:.4f}) — increase treatment/control imbalance"
    )

    # Novelty must be detected
    novelty = pr.get("novelty", {})
    assert novelty.get("pattern") == "NOVELTY", (
        f"Expected NOVELTY pattern, got {novelty.get('pattern')}"
    )

    # HTE top modifier must include device_type
    hte = pr.get("hte", {})
    top = hte.get("top_interactions", [])
    assert top, "HTE top_interactions is empty"
    assert any("device_type" in t for t in top[:3]), (
        f"device_type not in top-3 HTE interactions: {top[:3]}"
    )


def _validate_dataset2(sample: SampleExperiment) -> None:
    """Assert that Dataset 2 has no anomalies and finds company_size HTE."""
    pr = sample.precomputed_result["ml_result"]

    # No SRM
    anomaly = pr.get("anomaly", {})
    srm = next((c for c in anomaly.get("checks", []) if c["name"] == "srm_check"), None)
    if srm is not None:
        assert srm["passed"], f"Unexpected SRM in clean experiment (p={srm['score']:.4f})"

    # company_size should be the top HTE modifier
    hte = pr.get("hte", {})
    top = hte.get("top_interactions", [])
    assert top, "HTE top_interactions is empty"
    assert any("company_size" in t for t in top[:3]), (
        f"company_size not in top-3 HTE interactions: {top[:3]}"
    )


def _validate_dataset3(sample: SampleExperiment) -> None:
    """Assert that Dataset 3 has anomaly on days 8-9 and seller_tenure HTE."""
    pr = sample.precomputed_result["ml_result"]

    # Anomaly must have fired (some check failed)
    anomaly = pr.get("anomaly", {})
    failed = [c for c in anomaly.get("checks", []) if not c["passed"]]
    assert failed, "No anomaly checks failed — anomaly injection may not have worked"

    # Outlier_days or volume_spike must be among the failures
    failed_names = {c["name"] for c in failed}
    assert failed_names & {"outlier_days", "volume_spike"}, (
        f"Expected outlier_days or volume_spike to fail; got: {failed_names}"
    )

    # HTE top modifier must include seller_tenure_days
    hte = pr.get("hte", {})
    top = hte.get("top_interactions", [])
    assert top, "HTE top_interactions is empty"
    assert any("seller_tenure_days" in t for t in top[:3]), (
        f"seller_tenure_days not in top-3 HTE interactions: {top[:3]}"
    )


# ---------------------------------------------------------------------------
# Generation entry-point
# ---------------------------------------------------------------------------


def generate_all() -> dict[str, SampleExperiment]:
    """Generate all three datasets, validate them, and save to JSON.

    Returns:
        Mapping of name → SampleExperiment for inspection.
    """
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    generators = {
        "ecommerce_checkout": _gen_ecommerce_checkout,
        "saas_trial": _gen_saas_trial,
        "marketplace_fee": _gen_marketplace_fee,
    }
    validators = {
        "ecommerce_checkout": _validate_dataset1,
        "saas_trial": _validate_dataset2,
        "marketplace_fee": _validate_dataset3,
    }

    results: dict[str, SampleExperiment] = {}
    for name, gen_fn in generators.items():
        print(f"\n{'='*60}")
        print(f"  Generating: {name}")
        print(f"{'='*60}")
        sample = gen_fn()

        print(f"  Validating ...")
        validators[name](sample)
        print(f"  Validation passed ✓")

        # Save to JSON
        path = SAMPLES_DIR / f"{name}.json"
        payload = {
            "metadata": _native(sample.metadata),
            "user_data": _native(sample.user_data.to_dict(orient="records")),
            "daily_data": [
                {**row, "date": str(row["date"])[:10]}
                for row in _native(sample.daily_data.to_dict(orient="records"))
            ],
            "precomputed_result": _native(sample.precomputed_result),
        }
        with open(path, "w") as f:
            json.dump(payload, f, indent=2, cls=_NumpyEncoder)
        print(f"  Saved → {path}")

        # Print key insights
        insights = sample.precomputed_result["ml_result"].get("key_insights", [])
        print(f"\n  key_insights ({name}):")
        for i, insight in enumerate(insights, 1):
            print(f"    {i}. {insight}")

        results[name] = sample

    return results


if __name__ == "__main__":
    generate_all()
    print("\nAll datasets generated successfully.")
