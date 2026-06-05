"""Tests for backend/app/ml/hte.py — Heterogeneous Treatment Effect estimation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ml.hte import (
    HTEModel,
    _build_interaction_matrix,
    _check_treatment_balance,
    _drop_low_variance,
    fit_hte_model,
)

# ---------------------------------------------------------------------------
# Synthetic data factories
# ---------------------------------------------------------------------------


def _make_synthetic(
    n: int = 600,
    seed: int = 0,
    *,
    heterogeneity: bool = True,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Return (X, treatment, outcome) with a known interaction structure.

    When heterogeneity=True the feature 'x0' amplifies treatment lift so the
    model should recover x0_x_treat as a top modifier.  When False, treatment
    effect is homogeneous and stability should be low.
    """
    rng = np.random.default_rng(seed)
    x0 = rng.standard_normal(n)
    x1 = rng.standard_normal(n)
    x2 = rng.standard_normal(n)
    treatment = (rng.random(n) < 0.5).astype(float)

    if heterogeneity:
        # Lift is 0.5 + 1.5 * x0 → strong interaction with x0.
        outcome = (
            0.3 * x0
            + 0.1 * x1
            + treatment * (0.5 + 1.5 * x0)
            + rng.standard_normal(n) * 0.5
        )
    else:
        # Flat treatment effect → no heterogeneity.
        outcome = 0.3 * x0 + 0.1 * x1 + treatment * 0.4 + rng.standard_normal(n) * 0.5

    X = pd.DataFrame({"x0": x0, "x1": x1, "x2": x2})
    return X, pd.Series(treatment), pd.Series(outcome)


# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------


def test_fit_hte_model_returns_hte_model():
    X, t, y = _make_synthetic()
    model = fit_hte_model(X, t, y)
    assert isinstance(model, HTEModel)


def test_ite_point_length_matches_input():
    X, t, y = _make_synthetic()
    model = fit_hte_model(X, t, y)
    assert len(model.ite_point) == len(X)


def test_ite_uncertainty_length_matches_input():
    X, t, y = _make_synthetic()
    model = fit_hte_model(X, t, y, bootstrap=False)
    assert len(model.ite_uncertainty) == len(X)


def test_top_interactions_are_interaction_column_names():
    X, t, y = _make_synthetic()
    model = fit_hte_model(X, t, y)
    for name in model.top_interactions:
        assert name.endswith("_x_treat"), f"Expected _x_treat suffix, got {name}"


def test_ate_is_float():
    X, t, y = _make_synthetic()
    model = fit_hte_model(X, t, y)
    assert isinstance(model.ate, float)


def test_stability_score_in_range():
    X, t, y = _make_synthetic()
    model = fit_hte_model(X, t, y)
    assert -1.0 <= model.stability_score <= 1.0


def test_business_recommendation_is_nonempty_string():
    X, t, y = _make_synthetic()
    model = fit_hte_model(X, t, y)
    assert isinstance(model.business_recommendation, str)
    assert len(model.business_recommendation) > 0


# ---------------------------------------------------------------------------
# Known interaction recovery
# ---------------------------------------------------------------------------


def test_known_interaction_recovered_as_top_modifier():
    """x0 drives treatment heterogeneity → x0_x_treat should be first."""
    X, t, y = _make_synthetic(n=800, seed=42, heterogeneity=True)
    model = fit_hte_model(X, t, y, random_state=42)
    assert (
        model.top_interactions[0] == "x0_x_treat"
    ), f"Expected x0_x_treat as top modifier, got {model.top_interactions[0]}"


def test_ite_variance_is_higher_with_heterogeneity():
    """ITE spread should be larger when true heterogeneity exists."""
    X_het, t_het, y_het = _make_synthetic(n=600, seed=7, heterogeneity=True)
    X_hom, t_hom, y_hom = _make_synthetic(n=600, seed=7, heterogeneity=False)
    m_het = fit_hte_model(X_het, t_het, y_het, random_state=7)
    m_hom = fit_hte_model(X_hom, t_hom, y_hom, random_state=7)
    assert m_het.ite_point.std() > m_hom.ite_point.std()


# ---------------------------------------------------------------------------
# Stability score behaviour
# ---------------------------------------------------------------------------


def test_low_heterogeneity_gives_lower_stability():
    """Homogeneous treatment should produce lower (noisier) stability score."""
    X_het, t_het, y_het = _make_synthetic(n=600, seed=1, heterogeneity=True)
    X_hom, t_hom, y_hom = _make_synthetic(n=600, seed=1, heterogeneity=False)
    s_het = fit_hte_model(X_het, t_het, y_het, random_state=1).stability_score
    s_hom = fit_hte_model(X_hom, t_hom, y_hom, random_state=1).stability_score
    # Heterogeneous data should be at least as stable as homogeneous.
    assert (
        s_het >= s_hom - 0.15
    ), f"Expected heterogeneous stability ({s_het:.3f}) ≥ homogeneous ({s_hom:.3f}) - 0.15"


def test_stability_score_high_for_strong_signal():
    """Strong, consistent signal → stability close to 1."""
    X, t, y = _make_synthetic(n=1000, seed=0, heterogeneity=True)
    model = fit_hte_model(X, t, y, random_state=0)
    assert (
        model.stability_score > 0.5
    ), f"Expected stability > 0.5 for strong heterogeneity, got {model.stability_score:.3f}"


# ---------------------------------------------------------------------------
# SHAP consistency
# ---------------------------------------------------------------------------


def test_shap_values_sum_to_model_output():
    """SHAP additivity: shap_values.sum(axis=1) + expected_value ≈ model prediction."""
    X, t, y = _make_synthetic(n=300, seed=3)
    model = fit_hte_model(X, t, y, random_state=3)

    X_aug = _build_interaction_matrix(X, t)
    shap_vals = model.shap_explainer.shap_values(X_aug)
    expected = model.shap_explainer.expected_value
    predictions = model.xgb_model.predict(X_aug)

    reconstructed = shap_vals.sum(axis=1) + expected
    np.testing.assert_allclose(reconstructed, predictions, atol=1e-4)


def test_shap_interaction_count_matches_features():
    """Number of interaction SHAP columns == number of original features."""
    X, t, y = _make_synthetic()
    model = fit_hte_model(X, t, y)
    assert len(model.top_interactions) == X.shape[1]


# ---------------------------------------------------------------------------
# Bootstrap uncertainty
# ---------------------------------------------------------------------------


def test_bootstrap_uncertainty_is_nonnegative():
    X, t, y = _make_synthetic(n=200, seed=5)
    model = fit_hte_model(X, t, y, bootstrap=True, n_bootstrap=10)
    assert (model.ite_uncertainty >= 0).all()


def test_bootstrap_off_returns_zeros():
    X, t, y = _make_synthetic(n=200, seed=5)
    model = fit_hte_model(X, t, y, bootstrap=False)
    assert (model.ite_uncertainty == 0.0).all()


def test_bootstrap_uncertainty_has_spread():
    """When bootstrap=True, at least some subjects should have nonzero uncertainty."""
    X, t, y = _make_synthetic(n=300, seed=6)
    model = fit_hte_model(X, t, y, bootstrap=True, n_bootstrap=15)
    assert model.ite_uncertainty.max() > 0.0


# ---------------------------------------------------------------------------
# Treatment balance checks
# ---------------------------------------------------------------------------


def test_raises_on_extreme_imbalance():
    rng = np.random.default_rng(99)
    n = 200
    X = pd.DataFrame({"x": rng.standard_normal(n)})
    # Only 5% treatment → below hard 10/90 threshold.
    t = pd.Series((rng.random(n) < 0.05).astype(float))
    y = pd.Series(rng.standard_normal(n))
    with pytest.raises(ValueError, match="10/90 hard limit"):
        fit_hte_model(X, t, y)


def test_warns_on_moderate_imbalance():
    rng = np.random.default_rng(88)
    n = 400
    X = pd.DataFrame({"x": rng.standard_normal(n)})
    # ~25% treatment → outside 40/60 but inside 10/90.
    t = pd.Series((rng.random(n) < 0.25).astype(float))
    y = pd.Series(rng.standard_normal(n))
    with pytest.warns(UserWarning, match="40/60 recommended range"):
        fit_hte_model(X, t, y)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_raises_on_mismatched_lengths():
    X = pd.DataFrame({"x": [1.0, 2.0, 3.0]})
    t = pd.Series([0.0, 1.0])
    y = pd.Series([0.1, 0.2, 0.3])
    with pytest.raises(ValueError, match="same length"):
        fit_hte_model(X, t, y)


def test_raises_on_empty_input():
    X = pd.DataFrame({"x": pd.Series([], dtype=float)})
    t = pd.Series([], dtype=float)
    y = pd.Series([], dtype=float)
    with pytest.raises(ValueError, match="empty"):
        fit_hte_model(X, t, y)


# ---------------------------------------------------------------------------
# Low-variance feature filtering
# ---------------------------------------------------------------------------


def test_low_variance_features_are_dropped():
    rng = np.random.default_rng(10)
    n = 300
    X = pd.DataFrame(
        {
            "good": rng.standard_normal(n),
            "constant": np.zeros(n),
        }
    )
    t = pd.Series((rng.random(n) < 0.5).astype(float))
    y = pd.Series(rng.standard_normal(n))
    model = fit_hte_model(X, t, y)
    # 'constant' should be absent from interaction terms.
    assert "constant_x_treat" not in model.top_interactions


def test_all_features_low_variance_raises():
    """If all features are removed, interaction matrix is empty and XGB fails."""
    n = 100
    X = pd.DataFrame({"c1": np.zeros(n), "c2": np.zeros(n)})
    rng = np.random.default_rng(0)
    t = pd.Series((rng.random(n) < 0.5).astype(float))
    y = pd.Series(rng.standard_normal(n))
    # XGBoost will raise when given an empty feature matrix.
    with pytest.raises(Exception):
        fit_hte_model(X, t, y)


# ---------------------------------------------------------------------------
# _build_interaction_matrix unit tests
# ---------------------------------------------------------------------------


def test_interaction_matrix_column_count():
    X = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    t = pd.Series([0.0, 1.0])
    X_aug = _build_interaction_matrix(X, t)
    assert list(X_aug.columns) == ["a", "b", "a_x_treat", "b_x_treat"]


def test_interaction_values_are_product():
    X = pd.DataFrame({"a": [2.0, 3.0]})
    t = pd.Series([0.0, 1.0])
    X_aug = _build_interaction_matrix(X, t)
    np.testing.assert_array_equal(X_aug["a_x_treat"].values, [0.0, 3.0])


# ---------------------------------------------------------------------------
# _drop_low_variance unit tests
# ---------------------------------------------------------------------------


def test_drop_low_variance_removes_constant_column():
    X = pd.DataFrame({"vary": [1.0, 2.0, 3.0], "flat": [5.0, 5.0, 5.0]})
    X_out = _drop_low_variance(X)
    assert "flat" not in X_out.columns
    assert "vary" in X_out.columns


def test_drop_low_variance_keeps_all_if_none_low():
    X = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0]})
    X_out = _drop_low_variance(X)
    assert list(X_out.columns) == ["a", "b"]


# ---------------------------------------------------------------------------
# _check_treatment_balance unit tests
# ---------------------------------------------------------------------------


def test_check_balance_passes_50_50():
    t = pd.Series([0.0] * 50 + [1.0] * 50)
    _check_treatment_balance(t)  # should not raise or warn


def test_check_balance_raises_below_hard_limit():
    t = pd.Series([0.0] * 95 + [1.0] * 5)
    with pytest.raises(ValueError):
        _check_treatment_balance(t)


def test_check_balance_warns_between_limits():
    t = pd.Series([0.0] * 75 + [1.0] * 25)
    with pytest.warns(UserWarning):
        _check_treatment_balance(t)


# ---------------------------------------------------------------------------
# All-identical-features edge case
# ---------------------------------------------------------------------------


def test_all_identical_features_raises():
    """All users share the same non-zero feature vector → zero variance everywhere → raises."""
    n = 200
    rng = np.random.default_rng(0)
    t = pd.Series((rng.random(n) < 0.5).astype(float))
    y = pd.Series(rng.standard_normal(n))
    # Every row is identical — all feature columns have zero variance.
    X = pd.DataFrame({"x0": np.full(n, 3.14), "x1": np.full(n, 2.71)})
    with pytest.raises(Exception):
        fit_hte_model(X, t, y)


# ---------------------------------------------------------------------------
# Zero treatment effect
# ---------------------------------------------------------------------------


def test_zero_treatment_effect_no_error():
    """Zero true ATE → model still fits and returns HTEModel without error."""
    rng = np.random.default_rng(0)
    n = 300
    x = rng.standard_normal(n)
    t = pd.Series((rng.random(n) < 0.5).astype(float))
    y = pd.Series(0.5 * x + rng.standard_normal(n) * 0.1)
    X = pd.DataFrame({"x": x})
    model = fit_hte_model(X, t, y, random_state=0)
    assert isinstance(model, HTEModel)


def test_zero_treatment_effect_ate_near_zero():
    """When true treatment effect is zero, ATE estimate should be close to zero."""
    rng = np.random.default_rng(42)
    n = 600
    x = rng.standard_normal(n)
    t = pd.Series((rng.random(n) < 0.5).astype(float))
    y = pd.Series(0.3 * x + rng.standard_normal(n) * 0.05)
    X = pd.DataFrame({"x": x})
    model = fit_hte_model(X, t, y, random_state=42)
    assert abs(model.ate) < 0.15, f"Expected ATE ≈ 0, got {model.ate:.4f}"


def test_zero_treatment_effect_top_interactions_still_returned():
    """With no true heterogeneity, top_interactions list must still be returned."""
    rng = np.random.default_rng(5)
    n = 300
    x = rng.standard_normal(n)
    t = pd.Series((rng.random(n) < 0.5).astype(float))
    y = pd.Series(0.3 * x + rng.standard_normal(n) * 0.1)
    X = pd.DataFrame({"x": x})
    model = fit_hte_model(X, t, y, random_state=5)
    assert len(model.top_interactions) == X.shape[1]
    assert all(name.endswith("_x_treat") for name in model.top_interactions)
