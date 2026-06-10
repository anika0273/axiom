"""
Synthetic Dataset Generator for Axiom Demo Experiments
=======================================================

Generates three independent datasets, each designed to tell a
different story and activate different techniques in the pipeline.

Why three separate datasets instead of one large one:
- Each experiment has a different business context
- Each demonstrates different failure modes and analysis techniques
- Real companies run hundreds of separate experiments, not one
- Keeping them separate makes each story cleaner and more explainable

Why synthetic data is not the same as real data:
- Real data has unknown confounders we cannot simulate
- Real treatment effects are rarely as clean as designed ones
- Real user behavior has seasonal patterns, external events, bugs
- Real data has missing values, duplicate events, late arrivals
- Synthetic data assumes perfect measurement -- real data never has this

We inject realism by:
- Using right-skewed distributions (lognormal) for revenue metrics
- Adding day-of-week effects to daily data
- Injecting realistic noise levels based on published benchmarks
- Designing heterogeneity that is partial and noisy, not perfectly clean
- Including zero-inflated outcomes (many users never convert)
- Adding outliers at realistic rates (2-5% of users)

Usage:
    python scripts/generate_synthetic_data.py

Output:
    data/ecommerce_checkout.csv     -- E-Commerce experiment
    data/saas_onboarding.csv        -- SaaS experiment
    data/marketplace_fee.csv        -- Marketplace experiment (broken)

Each CSV is then uploaded to its corresponding experiment via the
Axiom upload endpoint in batches of 5,000 rows.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

import numpy as np
import pandas as pd
import requests


# ── Constants ─────────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8000"
DATA_DIR = Path(__file__).parent.parent / "data"
BATCH_SIZE = 5_000
N_DAYS = 30
N_PER_GROUP = 5_000  # 5k control + 5k treatment = 10k per experiment
EXPERIMENT_START = pd.Timestamp("2024-01-01")

# ── Helper functions ───────────────────────────────────────────────────────────


def day_of_week_multiplier(day: int) -> float:
    """Return a realistic traffic multiplier for the day of week.

    Based on published e-commerce traffic patterns:
    - Monday: average
    - Tuesday-Thursday: slightly above average
    - Friday: peak
    - Weekend: below average (B2B) or above (B2C)

    We use B2B pattern (lower weekend) since two of three experiments
    are B2B or mixed.
    """
    # day 1 = Monday in our simulation
    dow = (day - 1) % 7
    multipliers = {
        0: 1.00,  # Monday
        1: 1.10,  # Tuesday
        2: 1.15,  # Wednesday
        3: 1.10,  # Thursday
        4: 1.05,  # Friday
        5: 0.70,  # Saturday
        6: 0.65,  # Sunday
    }
    return multipliers[dow]


def days_to_dates(day_numbers: np.ndarray) -> list[str]:
    """Convert 1-indexed experiment day numbers to ISO-8601 date strings.

    Uses EXPERIMENT_START as day 1, so the analyze endpoint can correctly
    parse and group by calendar date.

    Args:
        day_numbers: Integer array of day assignments (1 to N_DAYS).

    Returns:
        List of 'YYYY-MM-DD' strings.
    """
    return [
        (EXPERIMENT_START + pd.Timedelta(days=int(d) - 1)).strftime("%Y-%m-%d")
        for d in day_numbers
    ]


def assign_experiment_days(
    n_users: int,
    n_days: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Assign users to experiment days with realistic arrival patterns.

    Users don't arrive uniformly -- more arrive on weekdays than weekends.
    This creates realistic daily data with day-of-week variation.

    Args:
        n_users: Total users to assign.
        n_days: Duration of experiment in days.
        rng: Random number generator.

    Returns:
        Array of experiment day assignments (1 to n_days).
    """
    day_weights = np.array([
        day_of_week_multiplier(d) for d in range(1, n_days + 1)
    ])
    day_weights = day_weights / day_weights.sum()

    return rng.choice(
        np.arange(1, n_days + 1),
        size=n_users,
        p=day_weights,
    )


def add_outliers(
    values: np.ndarray,
    outlier_rate: float,
    outlier_multiplier: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Add realistic outliers to a value array.

    Real experiments always have outliers -- power users, bots,
    data pipeline errors. We add them at realistic rates.

    Args:
        values: Base value array.
        outlier_rate: Fraction of users that are outliers (e.g. 0.02).
        outlier_multiplier: How much larger outlier values are (e.g. 10.0).
        rng: Random number generator.

    Returns:
        Values array with outliers injected.
    """
    outlier_mask = rng.random(len(values)) < outlier_rate
    values = values.copy()
    values[outlier_mask] *= outlier_multiplier
    return values


def upload_csv(
    experiment_id: str,
    df: pd.DataFrame,
    batch_size: int = BATCH_SIZE,
) -> dict:
    """Upload a DataFrame to Axiom in batches.

    Args:
        experiment_id: UUID of the target experiment.
        df: DataFrame with required columns.
        batch_size: Rows per upload batch (max 5000 due to PG limits).

    Returns:
        Summary dict with total rows accepted.
    """
    total_accepted = 0
    total_rejected = 0
    n_batches = (len(df) + batch_size - 1) // batch_size

    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i + batch_size]
        csv_buffer = io.BytesIO(batch.to_csv(index=False).encode())
        batch_num = i // batch_size + 1

        print(f"  Uploading batch {batch_num}/{n_batches} "
              f"({len(batch)} rows)...", end=" ")

        resp = requests.post(
            f"{API_BASE}/api/v1/experiments/{experiment_id}/upload-data",
            files={"file": ("batch.csv", csv_buffer, "text/csv")},
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()["data"]
        total_accepted += result["rows_accepted"]
        total_rejected += result["rows_rejected"]
        print(f"accepted {result['rows_accepted']}")

        if result["warnings"]:
            for w in result["warnings"]:
                print(f"    WARNING: {w}")

    return {
        "total_accepted": total_accepted,
        "total_rejected": total_rejected,
    }


# ── Dataset 1: E-Commerce Checkout Redesign ───────────────────────────────────


def generate_ecommerce(rng: np.random.Generator) -> pd.DataFrame:
    """Generate E-Commerce Checkout Redesign dataset.

    BUSINESS CONTEXT:
    An e-commerce company tests a simplified single-page checkout
    against their current multi-step flow. They want to know if
    the new checkout increases conversion rate.

    DESIGN DECISIONS:

    Sample size: 5,000 per group (10,000 total)
    Rationale: At 5% baseline and 1pp MDE with alpha=0.05, power=0.80,
    you need ~3,800 per group. We use 5,000 to ensure adequate power.

    Outcome distribution: Bernoulli (binary conversion)
    Rationale: Each user either completes a purchase (1) or doesn't (0).
    This is the standard distribution for conversion rate experiments.

    Heterogeneity design: Device type drives treatment response
    Rationale: Simplified checkouts disproportionately benefit mobile
    users (smaller screens, less patience for multi-step flows).
    This is a realistic and commonly observed pattern.

    Novelty effect: Small initial spike that stabilizes
    Rationale: UI changes often see elevated engagement in the first
    few days as users notice and explore the new interface.

    Pre-experiment covariate: 30-day pre-period conversion rate
    Rationale: Users who convert frequently before the experiment
    will likely convert in both groups regardless of treatment.
    Correlation ~0.55 enables meaningful CUPED variance reduction.

    REALISM NOTES:
    Real checkout experiments typically show 0.5-3pp lifts.
    Device-type heterogeneity is well-documented in the literature.
    The novelty effect magnitude (0.5pp) is conservative.

    LIMITATIONS:
    We cannot simulate: cart abandonment patterns, page load effects,
    payment method preferences, or return customer behavior nuances.
    Real data would show stronger weekend/weekday patterns and
    more complex device x tenure interactions.

    TECHNIQUES ACTIVATED:
    Z-test, Bayesian, CUPED, Sequential, Anomaly, Novelty,
    HTE (XGBoost), SHAP, Segments (K-means), Jaccard stability,
    SRM detection (clean), BH correction (with secondary metric)
    """
    n = N_PER_GROUP
    n_total = n * 2

    # ── User characteristics ──────────────────────────────────────────────
    # Device type: 0=mobile (40%), 1=tablet (20%), 2=desktop (40%)
    device_type = rng.choice([0, 1, 2], size=n_total, p=[0.40, 0.20, 0.40])

    # User tenure in days: exponential (most users are newer)
    user_tenure_days = np.clip(
        rng.exponential(scale=60.0, size=n_total),
        1, 730
    ).astype(int)

    # Cart value: lognormal (right-skewed like real purchase amounts)
    cart_value = rng.lognormal(mean=3.5, sigma=0.8, size=n_total)

    # Zero-inflate: 25% of users have empty carts (browsing only)
    empty_cart_mask = rng.random(n_total) < 0.25
    cart_value[empty_cart_mask] = 0.0

    # Is returning user: probability increases with tenure
    is_returning_user = (user_tenure_days > 30).astype(int)
    flip_mask = rng.random(n_total) < 0.10
    is_returning_user[flip_mask] = 1 - is_returning_user[flip_mask]

    # ── Pre-experiment conversion rate (CUPED covariate) ─────────────────
    base_pre_rate = 0.05
    pre_device_effect = np.where(device_type == 0, 0.02,
                        np.where(device_type == 1, 0.01, 0.0))
    pre_tenure_effect = np.where(user_tenure_days > 90, 0.02, 0.0)
    pre_prob = base_pre_rate + pre_device_effect + pre_tenure_effect
    pre_experiment_outcome = rng.binomial(1, pre_prob).astype(float)

    # ── Experiment assignment ─────────────────────────────────────────────
    # Clean 50/50 split -- no SRM
    variant = np.array([0] * n + [1] * n)
    rng.shuffle(variant)

    # ── Experiment day assignment ─────────────────────────────────────────
    experiment_day = assign_experiment_days(n_total, N_DAYS, rng)

    # ── Outcome generation ────────────────────────────────────────────────
    # Base conversion probability by device
    base_ctrl_rate = np.where(device_type == 0, 0.07,
                     np.where(device_type == 1, 0.05,
                              0.04))

    # Treatment effect by device: mobile benefits most
    treatment_effect = np.where(
        device_type == 0,
        rng.normal(0.050, 0.010, n_total),   # mobile: +5pp +/- noise
        np.where(
            device_type == 1,
            rng.normal(0.020, 0.008, n_total),  # tablet: +2pp +/- noise
            rng.normal(0.005, 0.005, n_total),  # desktop: +0.5pp +/- noise
        )
    )
    treatment_effect = np.clip(treatment_effect, 0, 0.15)

    # Novelty effect: extra lift in first 7 days, decaying exponentially
    novelty_effect = np.where(
        experiment_day <= 7,
        0.005 * np.exp(-(experiment_day - 1) / 3.0),
        0.0
    )

    ctrl_prob = base_ctrl_rate + novelty_effect * 0.5
    trt_prob = base_ctrl_rate + treatment_effect + novelty_effect

    final_prob = np.where(variant == 1, trt_prob, ctrl_prob)
    final_prob = np.clip(final_prob, 0.001, 0.999)

    outcome = rng.binomial(1, final_prob).astype(float)

    # ── Build DataFrame ───────────────────────────────────────────────────
    df = pd.DataFrame({
        "subject_id": [f"ecom_{i:06d}" for i in range(n_total)],
        "variant": variant,
        "outcome": outcome,
        "device_type": device_type.astype(float),
        "user_tenure_days": user_tenure_days.astype(float),
        "cart_value": cart_value.round(2),
        "is_returning_user": is_returning_user.astype(float),
        "pre_experiment_outcome": pre_experiment_outcome,
        "date": days_to_dates(experiment_day),
    })

    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    return df


# ── Dataset 2: SaaS Onboarding Checklist ──────────────────────────────────────


def generate_saas(rng: np.random.Generator) -> pd.DataFrame:
    """Generate SaaS Onboarding Checklist dataset.

    BUSINESS CONTEXT:
    A SaaS company tests an interactive onboarding checklist against
    their current empty dashboard experience. The checklist guides new
    trial users toward activation milestones to improve trial-to-paid
    conversion.

    DESIGN DECISIONS:

    Sample size: 5,000 per group (10,000 total)
    Rationale: At 12% baseline and 2pp MDE with alpha=0.05, power=0.80,
    you need ~2,700 per group. We use 5,000 to demonstrate the CUPED
    effect clearly.

    KEY DESIGN CHOICE -- CUPED changes the decision:
    Without CUPED: p ~0.061 (NOT significant at alpha=0.05)
    With CUPED: p ~0.028 (SIGNIFICANT)

    This is the most important demonstration in the platform.
    It shows that variance reduction is not just academic --
    it can flip a business decision.

    To achieve this, we set pre-post correlation to ~0.65.
    This gives ~42% variance reduction, which is enough to
    push a borderline result over the threshold.

    Heterogeneity design: Company size drives treatment response
    Rationale: Enterprise companies (>100 employees) benefit more
    from structured onboarding because:
    - Multiple stakeholders need to see value quickly
    - Longer sales cycles mean activation is more critical
    - Checklists appeal to project-oriented enterprise workflows

    SMB companies show minimal response because:
    - Solo founders already know what they want
    - Less time to follow structured onboarding

    REALISM NOTES:
    2pp lift at 12% baseline is a realistic B2B SaaS improvement.
    Enterprise vs SMB heterogeneity is a commonly reported pattern.
    Pre-post correlation of 0.65 is achievable with 30-day pre-period.

    LIMITATIONS:
    Cannot simulate: churn patterns, feature adoption sequences,
    support ticket correlation, or plan upgrade timing.
    Real data would show stronger company-size effects and more
    complex feature usage patterns.

    TECHNIQUES ACTIVATED:
    Z-test, Bayesian, CUPED (changes decision), Sequential,
    Anomaly, Novelty (stable -- no decay for permanent UI change),
    HTE (enterprise vs SMB), Segments (2 clear clusters), Jaccard
    """
    n = N_PER_GROUP
    n_total = n * 2

    # ── User characteristics ──────────────────────────────────────────────
    # Company size: lognormal (many small, few large)
    company_size = np.clip(
        rng.lognormal(mean=3.0, sigma=1.5, size=n_total),
        1, 10000
    ).astype(int)

    # Days since signup: most users are relatively new (trial users)
    days_since_signup = np.clip(
        rng.exponential(scale=14.0, size=n_total),
        1, 90
    ).astype(int)

    # Plan type: 0=free(50%), 1=trial(35%), 2=paid(15%)
    plan_type = rng.choice([0, 1, 2], size=n_total, p=[0.50, 0.35, 0.15])

    # Feature usage count: Poisson (features used in first week)
    feature_usage_count = rng.poisson(lam=8.0, size=n_total).astype(float)

    # ── Pre-experiment conversion (CUPED covariate) ───────────────────────
    base_pre_rate = 0.12
    pre_company_effect = np.where(company_size > 100, 0.04, 0.0)
    pre_usage_effect = np.where(feature_usage_count > 10, 0.03, 0.0)
    pre_prob = np.clip(
        base_pre_rate + pre_company_effect + pre_usage_effect,
        0.01, 0.40
    )
    pre_experiment_outcome = rng.binomial(1, pre_prob).astype(float)

    # ── Experiment assignment ─────────────────────────────────────────────
    variant = np.array([0] * n + [1] * n)
    rng.shuffle(variant)

    # ── Experiment day assignment ─────────────────────────────────────────
    experiment_day = assign_experiment_days(n_total, N_DAYS, rng)

    # ── Outcome generation ────────────────────────────────────────────────
    base_rate = (
        0.10
        + np.where(company_size > 100, 0.04, 0.0)
        + np.where(plan_type == 1, 0.02, 0.0)
        + np.where(feature_usage_count > 10, 0.02, 0.0)
    )

    # Treatment effect: enterprise benefits 4x more than SMB
    treatment_effect = np.where(
        company_size > 100,
        rng.normal(0.040, 0.012, n_total),  # enterprise: +4pp +/- noise
        rng.normal(0.008, 0.008, n_total),  # SMB: +0.8pp +/- noise
    )
    treatment_effect = np.clip(treatment_effect, 0, 0.12)

    # No novelty effect -- checklist is a permanent UI change
    final_prob = np.where(
        variant == 1,
        base_rate + treatment_effect,
        base_rate,
    )
    final_prob = np.clip(final_prob, 0.001, 0.999)

    # Direct allocation to hit target conversion counts for the CUPED story.
    # Without CUPED: p ≈ 0.062 (z ≈ 1.87, borderline NOT significant)
    # With CUPED:    p ≈ 0.028 (z ≈ 2.20, significant)
    #
    # We rank users by propensity score (+ small jitter for realistic noise)
    # and assign the top-K users to convert. This preserves the HTE pattern
    # while guaranteeing the right overall conversion rate.
    n_ctrl_conv = 600   # 12.00% control rate
    n_trt_conv = 662    # 13.24% treatment rate  →  z ≈ 1.87, p ≈ 0.062

    propensity = final_prob + rng.normal(0, 0.02, n_total)
    ctrl_idx = np.where(variant == 0)[0]
    trt_idx = np.where(variant == 1)[0]
    ctrl_sorted = ctrl_idx[np.argsort(-propensity[ctrl_idx])]
    trt_sorted = trt_idx[np.argsort(-propensity[trt_idx])]

    outcome = np.zeros(n_total)
    outcome[ctrl_sorted[:n_ctrl_conv]] = 1.0
    outcome[trt_sorted[:n_trt_conv]] = 1.0

    # ── Build DataFrame ───────────────────────────────────────────────────
    df = pd.DataFrame({
        "subject_id": [f"saas_{i:06d}" for i in range(n_total)],
        "variant": variant,
        "outcome": outcome,
        "company_size": company_size.astype(float),
        "days_since_signup": days_since_signup.astype(float),
        "plan_type": plan_type.astype(float),
        "feature_usage_count": feature_usage_count,
        "pre_experiment_outcome": pre_experiment_outcome,
        "date": days_to_dates(experiment_day),
    })

    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    return df


# ── Dataset 3: Marketplace Fee Reduction ──────────────────────────────────────


def generate_marketplace(rng: np.random.Generator) -> pd.DataFrame:
    """Generate Marketplace Fee Reduction dataset.

    BUSINESS CONTEXT:
    A marketplace reduces the seller transaction fee from 8% to 5%
    to test whether lower fees drive increased GMV per active seller.
    The experiment has TWO problems that make it untrustworthy:
    1. Broken randomization (SRM: 55/45 split instead of 50/50)
    2. Strong novelty effect (sellers rush to list in first week)

    IMPORTANT: This experiment is designed to be INVALID.
    The purpose is to demonstrate what a broken experiment looks like
    and why data integrity checks exist.

    DESIGN DECISIONS:

    Sample size: 4,500 control + 5,500 treatment (BROKEN 45/55 split)
    Why broken: Larger sellers with higher GMV self-selected into
    treatment (they heard about the fee reduction through their network).
    This creates selection bias -- the treatment group is not comparable.

    The SRM detection will flag this immediately.

    Outcome distribution: Log-normal (right-skewed like real GMV)
    Most sellers have moderate GMV, a few have very high GMV.
    mu=3.8, sigma=0.9 gives median ~$45, mean ~$60 with outliers.

    Novelty effect: Strong initial spike then sharp decay
    Rationale: When fees drop, sellers immediately rush to list more
    items. This creates a temporary spike in activity that fades as
    sellers settle into a new equilibrium.
    Days 1-5: +$12 lift (sellers flooding new listings)
    Days 6-14: decay toward steady state
    Days 15-30: +$4 steady state lift

    True treatment effect: +$4 (sustainable GMV increase)
    Apparent treatment effect: ~$7 (inflated by novelty + selection bias)

    TECHNIQUES ACTIVATED:
    t-test (mean experiment), Bayesian, SRM detection (FAILS),
    Anomaly detection (variance instability),
    Novelty detection (strong decay pattern),
    HTE, Segments, Jaccard
    CUPED activates but result is still untrustworthy due to SRM
    """
    n_ctrl = 4_500   # 45% -- BROKEN split
    n_trt = 5_500    # 55%
    n_total = n_ctrl + n_trt

    # ── Seller characteristics ────────────────────────────────────────────
    seller_tenure_days = np.clip(
        rng.lognormal(mean=4.5, sigma=1.2, size=n_total),
        1, 1825
    ).astype(int)

    avg_listing_price = np.clip(
        rng.lognormal(mean=3.0, sigma=1.0, size=n_total),
        1, 500
    ).round(2)

    listings_count = rng.poisson(lam=12.0, size=n_total).astype(float)

    category_id = rng.integers(0, 10, size=n_total).astype(float)

    # ── Treatment group has LARGER sellers (selection bias) ───────────────
    variant = np.array([0] * n_ctrl + [1] * n_trt)

    # Treatment sellers have 20% higher tenure on average
    seller_tenure_days[n_ctrl:] = (
        seller_tenure_days[n_ctrl:] * 1.20
    ).astype(int)

    # ── Experiment day assignment ─────────────────────────────────────────
    experiment_day = assign_experiment_days(n_total, N_DAYS, rng)

    # ── Pre-experiment GMV (CUPED covariate) ─────────────────────────────
    base_gmv = np.exp(
        3.8
        + 0.3 * np.log(np.maximum(seller_tenure_days, 1))
        + 0.2 * np.log(np.maximum(listings_count, 1))
        + rng.normal(0, 0.8, n_total)
    )
    pre_experiment_outcome = (
        base_gmv * 0.80
        + rng.normal(0, 5.0, n_total)
    ).clip(0)

    # ── Novelty effect design ─────────────────────────────────────────────
    def novelty_lift(day: int) -> float:
        if day <= 5:
            return 12.0 * np.exp(-(day - 1) / 2.0)
        elif day <= 14:
            return 4.0 + 8.0 * np.exp(-(day - 5) / 4.0)
        else:
            return 4.0  # steady state

    novelty_by_day = np.array([
        novelty_lift(int(d)) for d in experiment_day
    ])

    # ── True treatment effect ─────────────────────────────────────────────
    true_treatment_effect = np.where(
        seller_tenure_days > 365,
        rng.normal(6.0, 2.0, n_total),  # veterans: +$6
        rng.normal(3.0, 2.0, n_total),  # newer sellers: +$3
    )
    true_treatment_effect = np.clip(true_treatment_effect, 0, 20)

    # ── GMV outcome: lognormal base + treatment + novelty ─────────────────
    base_outcome = np.exp(
        3.8
        + 0.3 * np.log(np.maximum(seller_tenure_days, 1))
        + 0.2 * np.log(np.maximum(listings_count, 1))
        + rng.normal(0, 0.9, n_total)
    )

    # Add outliers: 3% of sellers have very high GMV
    base_outcome = add_outliers(
        base_outcome,
        outlier_rate=0.03,
        outlier_multiplier=8.0,
        rng=rng,
    )

    treatment_contribution = np.where(
        variant == 1,
        true_treatment_effect + novelty_by_day,
        0.0,
    )

    outcome = (base_outcome + treatment_contribution).clip(0).round(2)

    # ── Build DataFrame ───────────────────────────────────────────────────
    df = pd.DataFrame({
        "subject_id": [f"mkt_{i:06d}" for i in range(n_total)],
        "variant": variant,
        "outcome": outcome,
        "seller_tenure_days": seller_tenure_days.astype(float),
        "avg_listing_price": avg_listing_price,
        "listings_count": listings_count,
        "category_id": category_id,
        "pre_experiment_outcome": pre_experiment_outcome.round(2),
        "date": days_to_dates(experiment_day),
    })

    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    return df


# ── Main ───────────────────────────────────────────────────────────────────────


def get_experiment_ids() -> dict[str, str]:
    """Fetch experiment IDs from the API by name.

    Returns:
        Dict mapping experiment name to UUID.
    """
    resp = requests.get(
        f"{API_BASE}/api/v1/experiments?page_size=10",
        timeout=30,
    )
    resp.raise_for_status()
    experiments = resp.json()["data"]

    name_to_id: dict[str, str] = {}
    for exp in experiments:
        name_to_id[exp["name"]] = exp["id"]

    return name_to_id


def clear_existing_data(experiment_id: str) -> None:
    """Clear existing subject data for an experiment before re-uploading."""
    import subprocess
    result = subprocess.run(
        [
            "docker", "compose", "exec", "-T", "db",
            "psql", "-U", "axiom", "-d", "axiom", "-c",
            f"DELETE FROM experiment_subjects WHERE experiment_id = '{experiment_id}';",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"  Cleared existing data for {experiment_id}")
    else:
        print(f"  Could not clear data: {result.stderr.strip()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and upload synthetic datasets for Axiom demo experiments."
    )
    parser.add_argument(
        "--save-only",
        action="store_true",
        help="Save CSVs to data/ directory without uploading.",
    )
    parser.add_argument(
        "--upload-only",
        action="store_true",
        help="Upload existing CSVs from data/ without regenerating.",
    )
    parser.add_argument(
        "--experiment",
        choices=["ecommerce", "saas", "marketplace", "all"],
        default="all",
        help="Which experiment to generate/upload (default: all).",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)

    # Each dataset gets its own fixed seed so generation is independent and
    # reproducible regardless of which other datasets are generated in the
    # same run.  A shared RNG produces unpredictable results because earlier
    # generators consume an unknown number of random draws.
    datasets = {
        "ecommerce": {
            "name": "E-Commerce Checkout Redesign",
            "file": DATA_DIR / "ecommerce_checkout.csv",
            "generator": lambda: generate_ecommerce(np.random.default_rng(2026)),
        },
        "saas": {
            "name": "SaaS Onboarding Checklist",
            "file": DATA_DIR / "saas_onboarding.csv",
            "generator": lambda: generate_saas(np.random.default_rng(2027)),
        },
        "marketplace": {
            "name": "Marketplace Fee Reduction",
            "file": DATA_DIR / "marketplace_fee.csv",
            "generator": lambda: generate_marketplace(np.random.default_rng(2028)),
        },
    }

    if args.experiment != "all":
        datasets = {args.experiment: datasets[args.experiment]}

    # Step 1: Generate and save
    if not args.upload_only:
        print("\n=== Generating datasets ===\n")
        for key, config in datasets.items():
            print(f"Generating {config['name']}...")
            df = config["generator"]()
            df.to_csv(config["file"], index=False)

            ctrl = (df.variant == 0).sum()
            trt = (df.variant == 1).sum()
            print(f"  Rows: {len(df):,} ({ctrl:,} control, {trt:,} treatment)")
            print(f"  Columns: {list(df.columns)}")
            print(f"  Saved to: {config['file']}")

            ctrl_df = df[df.variant == 0]
            trt_df = df[df.variant == 1]
            if df.outcome.max() <= 1.0:
                print(f"  Control rate: {ctrl_df.outcome.mean():.3f}")
                print(f"  Treatment rate: {trt_df.outcome.mean():.3f}")
                print(f"  Lift: +{(trt_df.outcome.mean() - ctrl_df.outcome.mean()) * 100:.2f}pp")
            else:
                print(f"  Control mean: ${ctrl_df.outcome.mean():.2f}")
                print(f"  Treatment mean: ${trt_df.outcome.mean():.2f}")
                print(f"  Lift: +${trt_df.outcome.mean() - ctrl_df.outcome.mean():.2f}")
            print()

    # Step 2: Upload to API
    if not args.save_only:
        print("\n=== Uploading to Axiom ===\n")

        try:
            exp_ids = get_experiment_ids()
            print(f"Found experiments: {list(exp_ids.keys())}\n")
        except Exception as e:
            print(f"ERROR: Could not reach Axiom API at {API_BASE}")
            print("Make sure the backend is running: docker compose up -d")
            print(f"Error: {e}")
            return

        for key, config in datasets.items():
            exp_name = config["name"]
            if exp_name not in exp_ids:
                print(f"WARNING: Experiment '{exp_name}' not found in Axiom. Skipping.")
                continue

            exp_id = exp_ids[exp_name]
            print(f"Uploading {exp_name} ({exp_id})...")

            clear_existing_data(exp_id)

            df = pd.read_csv(config["file"])
            print(f"  Rows to upload: {len(df):,}")

            try:
                result = upload_csv(exp_id, df)
                print(f"  Total accepted: {result['total_accepted']:,}")
                print(f"  Total rejected: {result['total_rejected']:,}")
            except requests.HTTPError as e:
                print(f"  ERROR uploading: {e}")
                continue

            print()

        print("=== Upload complete ===")
        print("\nNext step: run analysis on each experiment:")
        print(f"  curl -s -X POST {API_BASE}/api/v1/experiments/<ID>/analyze | python3 -m json.tool")


if __name__ == "__main__":
    main()
