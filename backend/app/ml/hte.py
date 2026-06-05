"""
Heterogeneous Treatment Effect (HTE) estimation for A/B experiments.

# Causal note: valid only under randomization.
# Randomization → causal HTE. Observational data requires more assumptions.

Estimates individual-level treatment effects (ITE) using XGBoost with
treatment–feature interactions, ranks feature modifiers via SHAP, and
quantifies uncertainty through bootstrap resampling.

Usage::

    model = fit_hte_model(X, treatment, outcome)
    print(model.business_recommendation)
    # "Target top 20% of users by predicted lift; expected ATE +0.043"
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
import shap
from xgboost import XGBRegressor

from app.stats.testing import run_mean_test

logger = logging.getLogger(__name__)

_LOW_VARIANCE_THRESHOLD = 1e-8
_HIGH_CORRELATION_THRESHOLD = 0.9
_MIN_TREATMENT_FRACTION = 0.40  # warn below 40/60 balance
_MIN_TREATMENT_FRACTION_HARD = 0.10  # hard fail below 10/90


@dataclass
class HTEModel:
    """Fitted HTE model with causal estimates and business guidance.

    Attributes:
        xgb_model: Fitted XGBRegressor on treatment–feature interactions.
        shap_explainer: TreeExplainer bound to xgb_model.
        top_interactions: Feature names ranked by mean |SHAP| on interaction terms.
        ate: Average treatment effect (mean ITE over all subjects).
        ite_uncertainty: Per-subject ITE uncertainty (half-width of 90% bootstrap PI).
        stability_score: Correlation of ITEs across three independent refits (0–1).
        business_recommendation: Plain-language targeting recommendation.
        ite_point: Per-subject point estimate of individual treatment effect.
    """

    xgb_model: XGBRegressor
    shap_explainer: shap.TreeExplainer
    top_interactions: list[str]
    ate: float
    ite_uncertainty: pd.Series
    stability_score: float
    business_recommendation: str
    ite_point: pd.Series


def _check_treatment_balance(treatment: pd.Series) -> None:
    """Warn (or fail) if treatment assignment is severely imbalanced.

    Args:
        treatment: Binary 0/1 series indicating treatment assignment.

    Raises:
        ValueError: If treatment fraction is below the hard minimum (10/90).
    """
    frac = treatment.mean()
    if frac < _MIN_TREATMENT_FRACTION_HARD or frac > (1 - _MIN_TREATMENT_FRACTION_HARD):
        raise ValueError(
            f"Treatment fraction {frac:.2%} is outside the 10/90 hard limit. "
            "Check your assignment data."
        )
    if frac < _MIN_TREATMENT_FRACTION or frac > (1 - _MIN_TREATMENT_FRACTION):
        warnings.warn(
            f"Treatment fraction {frac:.2%} is outside the 40/60 recommended range. "
            "HTE estimates may be less reliable.",
            UserWarning,
            stacklevel=3,
        )


def _drop_low_variance(X: pd.DataFrame) -> pd.DataFrame:
    """Remove features with near-zero variance.

    Args:
        X: Feature matrix (numeric columns only; caller must pre-process).

    Returns:
        X with low-variance columns removed.
    """
    variances = X.var()
    low_var_cols = variances[variances < _LOW_VARIANCE_THRESHOLD].index.tolist()
    if low_var_cols:
        logger.warning("Dropping low-variance features: %s", low_var_cols)
        X = X.drop(columns=low_var_cols)
    return X


def _log_high_correlations(X: pd.DataFrame) -> None:
    """Log feature pairs whose absolute correlation exceeds the threshold.

    Args:
        X: Feature matrix.
    """
    if X.shape[1] < 2:
        return
    corr = X.corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    high = upper.stack()
    high = high[high > _HIGH_CORRELATION_THRESHOLD]
    for (f1, f2), val in high.items():
        logger.warning("High feature correlation (%.2f): %s — %s", val, f1, f2)


def _build_interaction_matrix(X: pd.DataFrame, treatment: pd.Series) -> pd.DataFrame:
    """Add treatment * feature interaction columns to the feature matrix.

    Args:
        X: Original feature matrix (caller must have pre-encoded categoricals).
        treatment: Binary 0/1 series.

    Returns:
        Augmented DataFrame with original columns plus interaction columns
        named ``<feature>_x_treat``.
    """
    t = treatment.values
    interaction_cols = {f"{col}_x_treat": X[col].values * t for col in X.columns}
    return pd.concat([X, pd.DataFrame(interaction_cols, index=X.index)], axis=1)


def _xgb_params(random_state: int) -> dict:
    return {
        "n_estimators": 200,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": random_state,
        "verbosity": 0,
    }


def _fit_single(
    X_aug: pd.DataFrame,
    outcome: pd.Series,
    random_state: int,
) -> XGBRegressor:
    model = XGBRegressor(**_xgb_params(random_state))
    model.fit(X_aug, outcome)
    return model


def _compute_ite(
    model: XGBRegressor, X: pd.DataFrame, treatment: pd.Series
) -> np.ndarray:
    """Estimate ITE as Y_hat(T=1, x) – Y_hat(T=0, x) for every subject.

    Args:
        model: Fitted XGBRegressor with interaction columns.
        X: Original feature matrix (no interaction columns).
        treatment: Binary 0/1 series (unused in prediction; kept for shape check).

    Returns:
        Array of per-subject ITE estimates.
    """
    t1 = pd.Series(np.ones(len(X), dtype=float), index=X.index)
    t0 = pd.Series(np.zeros(len(X), dtype=float), index=X.index)
    X_t1 = _build_interaction_matrix(X, t1)
    X_t0 = _build_interaction_matrix(X, t0)
    return model.predict(X_t1) - model.predict(X_t0)


def _bootstrap_uncertainty(
    X: pd.DataFrame,
    treatment: pd.Series,
    outcome: pd.Series,
    n_boot: int,
    random_state: int,
) -> pd.Series:
    """Estimate per-subject ITE uncertainty via bootstrap.

    Args:
        X: Feature matrix.
        treatment: Binary 0/1 series.
        outcome: Continuous outcome series.
        n_boot: Number of bootstrap resamples.
        random_state: Seed for reproducibility.

    Returns:
        Per-subject half-width of the 90% bootstrap prediction interval.
    """
    rng = np.random.default_rng(random_state)
    ite_samples: list[np.ndarray] = []
    n = len(X)

    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        X_b = X.iloc[idx].reset_index(drop=True)
        t_b = treatment.iloc[idx].reset_index(drop=True)
        y_b = outcome.iloc[idx].reset_index(drop=True)

        # Skip bootstrap samples with degenerate treatment assignment.
        if t_b.mean() < 0.05 or t_b.mean() > 0.95:
            continue

        X_aug_b = _build_interaction_matrix(X_b, t_b)
        m = XGBRegressor(**_xgb_params(random_state + i))
        m.fit(X_aug_b, y_b)
        ite_samples.append(_compute_ite(m, X, treatment))

    if not ite_samples:
        return pd.Series(np.zeros(n), index=X.index)

    ite_matrix = np.stack(ite_samples, axis=0)  # (n_boot, n_subjects)
    half_width = (
        np.percentile(ite_matrix, 95, axis=0) - np.percentile(ite_matrix, 5, axis=0)
    ) / 2.0
    return pd.Series(half_width, index=X.index)


def _stability_score(
    X: pd.DataFrame,
    treatment: pd.Series,
    outcome: pd.Series,
    random_state: int,
) -> float:
    """Measure ITE consistency across three independent model refits.

    Fits the model three times with different random seeds and returns the
    mean pairwise Pearson correlation of the resulting ITE vectors.  A score
    close to 1 indicates stable, reproducible heterogeneity; a low score
    suggests the model is fitting noise.

    Args:
        X: Feature matrix.
        treatment: Binary 0/1 series.
        outcome: Continuous outcome series.
        random_state: Base seed (each refit uses random_state + i).

    Returns:
        Mean pairwise correlation in [0, 1].
    """
    ites: list[np.ndarray] = []
    for i in range(3):
        X_aug = _build_interaction_matrix(X, treatment)
        m = _fit_single(X_aug, outcome, random_state=random_state + i * 17)
        ites.append(_compute_ite(m, X, treatment))

    pairs = [(0, 1), (0, 2), (1, 2)]
    correlations: list[float] = []
    for a, b in pairs:
        if np.std(ites[a]) < 1e-10 or np.std(ites[b]) < 1e-10:
            correlations.append(0.0)
        else:
            correlations.append(float(np.corrcoef(ites[a], ites[b])[0, 1]))
    return float(np.mean(correlations))


def _build_recommendation(
    ite_point: np.ndarray,
    ate: float,
    top_features: list[str],
) -> str:
    """Generate a plain-language targeting recommendation.

    Args:
        ite_point: Per-subject ITE estimates.
        ate: Average treatment effect.
        top_features: Top interaction features by SHAP importance.

    Returns:
        Human-readable recommendation string.
    """
    top_20_threshold = float(np.percentile(ite_point, 80))
    top_20_avg_lift = float(np.mean(ite_point[ite_point >= top_20_threshold]))
    sign = "+" if ate >= 0 else ""
    feature_hint = f" driven by {top_features[0]}" if top_features else ""

    return (
        f"Target top 20% of users by predicted lift (ITE ≥ {top_20_threshold:.3f}); "
        f"expected lift for this segment: {top_20_avg_lift:+.3f}{feature_hint}. "
        f"Overall ATE: {sign}{ate:.3f}."
    )


def fit_hte_model(
    X: pd.DataFrame,
    treatment: pd.Series,
    outcome: pd.Series,
    random_state: int = 42,
    bootstrap: bool = False,
    n_bootstrap: int = 100,
) -> HTEModel:
    """Fit a Heterogeneous Treatment Effect model on randomized A/B data.

    Assumes features in X are already processed (numeric; no categorical encoding
    is performed here).  Constructs treatment–feature interactions internally.

    # Causal note: Randomization → causal HTE. Observational data requires more assumptions.

    Args:
        X: User feature matrix (numeric columns only; pre-processed by caller).
        treatment: Binary Series (0 = control, 1 = treatment), same index as X.
        outcome: Continuous outcome Series (e.g. revenue, conversion), same index as X.
        random_state: Seed for all stochastic operations. Default 42.
        bootstrap: If True, run bootstrap uncertainty estimation. Default False
            (too slow for real-time API use; enable for offline analysis).
        n_bootstrap: Number of bootstrap resamples when bootstrap=True. Default 100.

    Returns:
        HTEModel with point ITE estimates, uncertainty, SHAP attribution,
        stability score, and a business recommendation.

    Raises:
        ValueError: If treatment fraction is below the hard 10/90 threshold,
            or if X and treatment/outcome have mismatched lengths.
    """
    if len(X) != len(treatment) or len(X) != len(outcome):
        raise ValueError(
            f"X ({len(X)}), treatment ({len(treatment)}), and outcome ({len(outcome)}) "
            "must have the same length."
        )
    if len(X) == 0:
        raise ValueError("X must not be empty.")

    treatment = treatment.reset_index(drop=True)
    outcome = outcome.reset_index(drop=True)
    X = X.reset_index(drop=True)

    _check_treatment_balance(treatment)

    X_clean = _drop_low_variance(X)
    _log_high_correlations(X_clean)

    # Validate that enough data exists in each arm for significance testing.
    n_treat = int(treatment.sum())
    n_ctrl = len(treatment) - n_treat
    if n_treat < 2 or n_ctrl < 2:
        raise ValueError("Need at least 2 subjects in each arm to fit HTE model.")

    # Build augmented feature matrix with interaction columns.
    X_aug = _build_interaction_matrix(X_clean, treatment)

    # Fit primary model.
    model = _fit_single(X_aug, outcome, random_state)

    # Per-subject ITE point estimates.
    ite_arr = _compute_ite(model, X_clean, treatment)
    ite_point = pd.Series(ite_arr, index=X.index)

    # ATE via run_mean_test for consistency with the stats engine.
    ctrl_outcomes = outcome[treatment == 0].values
    treat_outcomes = outcome[treatment == 1].values
    test_result = run_mean_test(ctrl_outcomes, treat_outcomes)
    ate = float(test_result.lift_abs)

    # SHAP on interaction columns to rank feature modifiers.
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_aug)  # (n_subjects, n_features_aug)

    interaction_col_names = [c for c in X_aug.columns if c.endswith("_x_treat")]
    interaction_indices = [X_aug.columns.get_loc(c) for c in interaction_col_names]
    mean_abs_shap = np.abs(shap_values[:, interaction_indices]).mean(axis=0)
    ranked_idx = np.argsort(mean_abs_shap)[::-1]
    top_interactions = [interaction_col_names[i] for i in ranked_idx]

    # Bootstrap uncertainty (optional — off by default for API latency).
    if bootstrap:
        ite_uncertainty = _bootstrap_uncertainty(
            X_clean, treatment, outcome, n_boot=n_bootstrap, random_state=random_state
        )
    else:
        ite_uncertainty = pd.Series(np.zeros(len(X)), index=X.index)

    # Stability score from three independent refits.
    stability = _stability_score(X_clean, treatment, outcome, random_state)

    recommendation = _build_recommendation(ite_arr, ate, top_interactions)

    return HTEModel(
        xgb_model=model,
        shap_explainer=explainer,
        top_interactions=top_interactions,
        ate=ate,
        ite_uncertainty=ite_uncertainty,
        stability_score=stability,
        business_recommendation=recommendation,
        ite_point=ite_point,
    )
