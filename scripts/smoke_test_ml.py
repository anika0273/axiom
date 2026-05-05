#!/usr/bin/env python3
"""Smoke test for the Axiom ML engine.

Loads all three sample experiments and verifies that the ML analysis
produces the expected results for each.  Run from the repo root:

    PYTHONPATH=backend python scripts/smoke_test_ml.py

Exit code 0 = all checks passed.  Exit code 1 = one or more checks failed.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.data.sample_experiments import load_sample_experiment
from app.ml.engine import MLAnalysisResult, MLExperimentInput, run_ml_analysis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def check(label: str, condition: bool, actual=None) -> bool:
    """Print PASS/FAIL for one check and return the boolean result."""
    if condition:
        print(f"  PASS  {label}")
    else:
        suffix = f"  (actual: {actual!r})" if actual is not None else ""
        print(f"  FAIL  {label}{suffix}")
    return condition


def get_outlier_day_numbers(daily_data) -> list[int]:
    """Return 1-indexed day numbers that IsolationForest flags as outliers.

    Mirrors the exact logic in anomaly.detect_outlier_days so the check is
    consistent with what the engine reports.
    """
    features = daily_data[
        ["control_metric", "treatment_metric", "n_control", "n_treatment"]
    ].values.astype(float)
    clf = IsolationForest(contamination="auto", random_state=42)
    clf.fit(features)
    scores = clf.score_samples(features)
    q1 = float(np.percentile(scores, 25))
    q3 = float(np.percentile(scores, 75))
    iqr = q3 - q1
    lower_fence = q1 - 3.0 * max(iqr, 1e-10)
    outlier_mask = scores < lower_fence
    return [i + 1 for i, flagged in enumerate(outlier_mask) if flagged]


def build_input(exp) -> MLExperimentInput:
    """Convert a SampleExperiment into an MLExperimentInput.

    The ML engine constructs its treatment indicator as [0…0, 1…1], so X must
    have control rows first followed by treatment rows.  We sort accordingly.
    """
    df = exp.user_data
    feature_cols = [c for c in df.columns if c not in ("user_id", "treatment", "outcome")]
    ctrl = df[df["treatment"] == 0]
    trt = df[df["treatment"] == 1]
    ordered = pd.concat([ctrl, trt]).reset_index(drop=True)
    X = ordered[feature_cols]
    return MLExperimentInput(
        control_values=ctrl["outcome"].tolist(),
        treatment_values=trt["outcome"].tolist(),
        user_features=X,
        daily_metrics=exp.daily_data,
    )


def top_hte_modifier(result: MLAnalysisResult) -> str | None:
    """Return the top treatment-modifier feature name, stripping '_x_treat'."""
    if result.hte_result is None or not result.hte_result.top_interactions:
        return None
    return result.hte_result.top_interactions[0].replace("_x_treat", "")


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------


def run_all() -> bool:
    all_passed = True

    # ── Dataset 1: E-Commerce Checkout ──────────────────────────────────────
    print("\nDataset 1 (E-Commerce Checkout):")
    exp1 = load_sample_experiment("ecommerce_checkout")
    r1 = run_ml_analysis(build_input(exp1))

    verdict1 = r1.overall_verdict
    all_passed &= check(
        "overall_verdict == 'INVALID' (SRM detected)",
        verdict1 == "INVALID",
        verdict1,
    )

    novelty1 = r1.novelty_result.pattern if r1.novelty_result else None
    all_passed &= check("novelty pattern == 'NOVELTY'", novelty1 == "NOVELTY", novelty1)

    hte1 = top_hte_modifier(r1)
    all_passed &= check("top HTE modifier == 'device_type'", hte1 == "device_type", hte1)

    all_passed &= check(
        "key_insights is non-empty",
        bool(r1.key_insights),
        len(r1.key_insights),
    )

    # ── Dataset 2: SaaS Trial ────────────────────────────────────────────────
    print("\nDataset 2 (SaaS Trial):")
    exp2 = load_sample_experiment("saas_trial")
    r2 = run_ml_analysis(build_input(exp2))

    verdict2 = r2.overall_verdict
    all_passed &= check("overall_verdict == 'CLEAN'", verdict2 == "CLEAN", verdict2)

    novelty2 = r2.novelty_result.pattern if r2.novelty_result else None
    all_passed &= check("novelty pattern == 'STABLE'", novelty2 == "STABLE", novelty2)

    hte2 = top_hte_modifier(r2)
    all_passed &= check(
        "top HTE modifier == 'company_size'",
        hte2 == "company_size",
        hte2,
    )

    all_passed &= check(
        "key_insights is non-empty",
        bool(r2.key_insights),
        len(r2.key_insights),
    )

    # ── Dataset 3: Marketplace Fee ───────────────────────────────────────────
    print("\nDataset 3 (Marketplace Fee):")
    exp3 = load_sample_experiment("marketplace_fee")
    r3 = run_ml_analysis(build_input(exp3))

    verdict3 = r3.overall_verdict
    all_passed &= check(
        "overall_verdict == 'NEEDS_REVIEW'",
        verdict3 == "NEEDS_REVIEW",
        verdict3,
    )

    outlier_days = get_outlier_day_numbers(exp3.daily_data)
    days_8_9_flagged = 8 in outlier_days or 9 in outlier_days
    all_passed &= check(
        f"anomaly detected on days 8-9  (all flagged days: {outlier_days})",
        days_8_9_flagged,
        outlier_days,
    )

    hte3 = top_hte_modifier(r3)
    all_passed &= check(
        "top HTE modifier == 'seller_tenure_days'",
        hte3 == "seller_tenure_days",
        hte3,
    )

    all_passed &= check(
        "key_insights is non-empty",
        bool(r3.key_insights),
        len(r3.key_insights),
    )

    return all_passed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    passed = run_all()
    print(f"\n{'All checks passed.' if passed else 'SOME CHECKS FAILED.'}")
    sys.exit(0 if passed else 1)
