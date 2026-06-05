"""Tests for backend/app/data/sample_experiments.py.

All tests load from the pre-generated JSON files; no DB connection required.
Seeder idempotency is tested via AsyncMock — no live Postgres needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.data.sample_experiments import SampleExperiment, load_sample_experiment

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_NAMES = ["ecommerce_checkout", "saas_trial", "marketplace_fee"]


@pytest.fixture(scope="session")
def eco() -> SampleExperiment:
    return load_sample_experiment("ecommerce_checkout")


@pytest.fixture(scope="session")
def saas() -> SampleExperiment:
    return load_sample_experiment("saas_trial")


@pytest.fixture(scope="session")
def mkt() -> SampleExperiment:
    return load_sample_experiment("marketplace_fee")


# ---------------------------------------------------------------------------
# 1. Load without error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", SAMPLE_NAMES)
def test_loads_without_error(name: str) -> None:
    sample = load_sample_experiment(name)
    assert isinstance(sample, SampleExperiment)
    assert isinstance(sample.user_data, pd.DataFrame)
    assert isinstance(sample.daily_data, pd.DataFrame)
    assert isinstance(sample.precomputed_result, dict)
    assert isinstance(sample.metadata, dict)


# ---------------------------------------------------------------------------
# 2. User-level data: shape, nulls, valid ranges
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", SAMPLE_NAMES)
def test_user_data_no_nulls(name: str) -> None:
    df = load_sample_experiment(name).user_data
    assert df.isnull().sum().sum() == 0, f"{name}: nulls found in user_data"


@pytest.mark.parametrize("name", SAMPLE_NAMES)
def test_user_data_required_columns(name: str) -> None:
    df = load_sample_experiment(name).user_data
    for col in ("user_id", "treatment", "outcome"):
        assert col in df.columns, f"{name}: missing column {col}"


def test_eco_user_data_shape(eco: SampleExperiment) -> None:
    df = eco.user_data
    assert len(df) == 10_000
    assert set(df["treatment"].unique()).issubset({0, 1})
    assert set(df["outcome"].unique()).issubset({0, 1})
    # device_type encoding: 1=mobile, 0=desktop
    assert set(df["device_type"].unique()).issubset({0, 1})
    assert df["user_age_days"].min() >= 0
    assert df["user_age_days"].max() <= 365
    assert df["cart_value"].min() >= 1.0
    assert df["n_prior_orders"].min() >= 0


def test_saas_user_data_shape(saas: SampleExperiment) -> None:
    df = saas.user_data
    assert len(df) == 5_000
    assert set(df["treatment"].unique()).issubset({0, 1})
    assert set(df["outcome"].unique()).issubset({0, 1})
    assert df["company_size"].min() >= 1.0
    assert df["company_size"].max() <= 500.0
    assert df["usage_score"].min() >= 0.0
    assert df["usage_score"].max() <= 100.0


def test_mkt_user_data_shape(mkt: SampleExperiment) -> None:
    df = mkt.user_data
    assert len(df) == 20_000
    assert set(df["treatment"].unique()).issubset({0, 1})
    assert df["outcome"].min() > 0  # GMV is always positive
    assert df["seller_tenure_days"].min() >= 0
    assert df["seller_tenure_days"].max() <= 1000
    assert df["avg_rating"].min() >= 3.0
    assert df["avg_rating"].max() <= 5.0
    assert df["n_listings"].min() >= 0


# ---------------------------------------------------------------------------
# 3. Daily data: date range, no negatives, day-of-week traffic pattern
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,n_days",
    [("ecommerce_checkout", 21), ("saas_trial", 30), ("marketplace_fee", 28)],
)
def test_daily_data_length(name: str, n_days: int) -> None:
    df = load_sample_experiment(name).daily_data
    assert len(df) == n_days, f"{name}: expected {n_days} rows, got {len(df)}"


@pytest.mark.parametrize("name", SAMPLE_NAMES)
def test_daily_data_required_columns(name: str) -> None:
    df = load_sample_experiment(name).daily_data
    for col in (
        "date",
        "control_metric",
        "treatment_metric",
        "n_control",
        "n_treatment",
    ):
        assert col in df.columns, f"{name}: missing daily column {col}"


@pytest.mark.parametrize("name", SAMPLE_NAMES)
def test_daily_data_no_negatives(name: str) -> None:
    df = load_sample_experiment(name).daily_data
    assert (df["n_control"] > 0).all(), f"{name}: non-positive n_control"
    assert (df["n_treatment"] > 0).all(), f"{name}: non-positive n_treatment"
    assert (df["control_metric"] > 0).all(), f"{name}: non-positive control_metric"
    assert (df["treatment_metric"] > 0).all(), f"{name}: non-positive treatment_metric"


def test_eco_weekend_lower_traffic(eco: SampleExperiment) -> None:
    """Weekends should have lower n_control + n_treatment than weekday average."""
    df = eco.daily_data.copy()
    df["dow"] = df["date"].dt.dayofweek
    df["total_traffic"] = df["n_control"] + df["n_treatment"]
    weekend = df[df["dow"] >= 5]["total_traffic"].mean()
    weekday = df[df["dow"] < 5]["total_traffic"].mean()
    assert (
        weekend < weekday
    ), f"Weekend traffic ({weekend:.1f}) should be lower than weekday ({weekday:.1f})"


def test_saas_monday_higher_than_friday(saas: SampleExperiment) -> None:
    """B2B SaaS: Monday signups should exceed Friday signups."""
    df = saas.daily_data.copy()
    df["dow"] = df["date"].dt.dayofweek
    df["total"] = df["n_control"] + df["n_treatment"]
    mon = df[df["dow"] == 0]["total"].mean()
    fri = df[df["dow"] == 4]["total"].mean()
    assert (
        mon > fri
    ), f"Monday ({mon:.1f}) should have more signups than Friday ({fri:.1f})"


def test_mkt_anomaly_days_high_volume(mkt: SampleExperiment) -> None:
    """Days 8 and 9 should have 5x the normal volume."""
    df = mkt.daily_data.reset_index(drop=True)
    normal_median = df.drop(index=[8, 9])["n_control"].median()
    for day in (8, 9):
        assert df.loc[day, "n_control"] > normal_median * 3, (
            f"Day {day} n_control ({df.loc[day, 'n_control']}) "
            f"not visibly elevated vs median ({normal_median})"
        )


# ---------------------------------------------------------------------------
# 4. Feature correlation checks (expected direction)
# ---------------------------------------------------------------------------


def test_eco_age_vs_orders_positive_corr(eco: SampleExperiment) -> None:
    df = eco.user_data
    corr = df["user_age_days"].corr(df["n_prior_orders"])
    assert (
        corr > 0.20
    ), f"corr(user_age_days, n_prior_orders) = {corr:.3f}, expected > 0.20"


def test_saas_company_size_vs_usage_positive_corr(saas: SampleExperiment) -> None:
    df = saas.user_data
    corr = df["company_size"].corr(df["usage_score"])
    assert corr > 0.10, f"corr(company_size, usage_score) = {corr:.3f}, expected > 0.10"


def test_mkt_tenure_vs_rating_positive_corr(mkt: SampleExperiment) -> None:
    df = mkt.user_data
    corr = df["seller_tenure_days"].corr(df["avg_rating"])
    assert (
        corr > 0.20
    ), f"corr(seller_tenure_days, avg_rating) = {corr:.3f}, expected > 0.20"


# ---------------------------------------------------------------------------
# 5. Dataset 1: SRM detected + novelty pattern
# ---------------------------------------------------------------------------


def test_eco_srm_detected(eco: SampleExperiment) -> None:
    anomaly = eco.precomputed_result["ml_result"].get("anomaly", {})
    checks = anomaly.get("checks", [])
    srm = next((c for c in checks if c["name"] == "srm_check"), None)
    assert srm is not None, "srm_check missing from anomaly checks"
    assert not srm[
        "passed"
    ], f"SRM check unexpectedly passed (p={srm['score']:.4f}) for 55/45 split"


def test_eco_novelty_pattern(eco: SampleExperiment) -> None:
    novelty = eco.precomputed_result["ml_result"].get("novelty", {})
    assert (
        novelty.get("pattern") == "NOVELTY"
    ), f"Expected NOVELTY pattern, got {novelty.get('pattern')}"


def test_eco_hte_device_type(eco: SampleExperiment) -> None:
    hte = eco.precomputed_result["ml_result"].get("hte", {})
    top = hte.get("top_interactions", [])
    assert top, "HTE top_interactions is empty"
    assert (
        "device_type" in top[0]
    ), f"Expected device_type as #1 HTE modifier, got: {top[:3]}"


# ---------------------------------------------------------------------------
# 6. Dataset 2: clean experiment — VALID/CLEAN verdict
# ---------------------------------------------------------------------------


def test_saas_no_srm(saas: SampleExperiment) -> None:
    anomaly = saas.precomputed_result["ml_result"].get("anomaly", {})
    checks = anomaly.get("checks", [])
    srm = next((c for c in checks if c["name"] == "srm_check"), None)
    if srm is not None:
        assert srm[
            "passed"
        ], f"Unexpected SRM in clean 50/50 experiment (p={srm['score']:.4f})"


def test_saas_stable_novelty(saas: SampleExperiment) -> None:
    novelty = saas.precomputed_result["ml_result"].get("novelty", {})
    assert (
        novelty.get("pattern") == "STABLE"
    ), f"Expected STABLE novelty, got {novelty.get('pattern')}"


def test_saas_hte_company_size(saas: SampleExperiment) -> None:
    hte = saas.precomputed_result["ml_result"].get("hte", {})
    top = hte.get("top_interactions", [])
    assert top, "HTE top_interactions is empty for saas_trial"
    assert (
        "company_size" in top[0]
    ), f"Expected company_size as #1 HTE modifier, got: {top[:3]}"


def test_saas_overall_verdict_clean(saas: SampleExperiment) -> None:
    verdict = saas.precomputed_result["ml_result"]["overall_verdict"]
    assert verdict in (
        "CLEAN",
        "NEEDS_REVIEW",
    ), f"Unexpected verdict for clean experiment: {verdict}"
    # Must NOT be INVALID
    assert verdict != "INVALID"


# ---------------------------------------------------------------------------
# 7. Dataset 3: anomaly on days 8-9 + seller_tenure_days HTE
# ---------------------------------------------------------------------------


def test_mkt_anomaly_detected(mkt: SampleExperiment) -> None:
    anomaly = mkt.precomputed_result["ml_result"].get("anomaly", {})
    failed = [c for c in anomaly.get("checks", []) if not c["passed"]]
    assert failed, "No anomaly checks failed — 5x volume spike not detected"


def test_mkt_outlier_or_volume_spike(mkt: SampleExperiment) -> None:
    anomaly = mkt.precomputed_result["ml_result"].get("anomaly", {})
    failed_names = {c["name"] for c in anomaly.get("checks", []) if not c["passed"]}
    assert failed_names & {
        "outlier_days",
        "volume_spike",
    }, f"Expected outlier_days or volume_spike to fail; failed: {failed_names}"


def test_mkt_hte_seller_tenure(mkt: SampleExperiment) -> None:
    hte = mkt.precomputed_result["ml_result"].get("hte", {})
    top = hte.get("top_interactions", [])
    assert top, "HTE top_interactions is empty for marketplace_fee"
    assert (
        "seller_tenure_days" in top[0]
    ), f"Expected seller_tenure_days as #1 HTE modifier, got: {top[:3]}"


def test_mkt_established_sellers_positive_hte(mkt: SampleExperiment) -> None:
    """Established sellers (tenure > 180) should have higher conversion."""
    df = mkt.user_data
    est = df[df["seller_tenure_days"] > 180]
    new = df[df["seller_tenure_days"] <= 180]
    est_ate = (
        est[est.treatment == 1]["outcome"].mean()
        - est[est.treatment == 0]["outcome"].mean()
    )
    new_ate = (
        new[new.treatment == 1]["outcome"].mean()
        - new[new.treatment == 0]["outcome"].mean()
    )
    assert (
        est_ate > new_ate
    ), f"Established ATE ({est_ate:.2f}) should exceed new-seller ATE ({new_ate:.2f})"


# ---------------------------------------------------------------------------
# 8. Seeder idempotency (mocked DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seeder_idempotent() -> None:
    """Calling seed_sample_experiments twice inserts each experiment only once."""
    from app.data.sample_experiments import seed_sample_experiments

    insert_count = 0

    class FakeResult:
        def scalars(self) -> "FakeResult":
            return self

        def first(self) -> None:
            return None  # Always "not found" → triggers insert

    class FakeResult2:
        def scalars(self) -> "FakeResult2":
            return self

        def first(self) -> object:
            return object()  # "found" → skip insert

    db = AsyncMock()

    # First call: experiment not found → insert
    db.execute = AsyncMock(return_value=FakeResult())

    def _add(obj: object) -> None:
        nonlocal insert_count
        from app.models.experiment import Experiment

        if isinstance(obj, Experiment):
            insert_count += 1

    db.add = MagicMock(side_effect=_add)
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    with patch("app.data.sample_experiments.load_sample_experiment") as mock_load:
        # Return a minimal mock SampleExperiment for each name
        def _make_sample(name: str) -> SampleExperiment:
            import pandas as pd

            return SampleExperiment(
                user_data=pd.DataFrame(),
                daily_data=pd.DataFrame(),
                precomputed_result={},
                metadata={
                    "name": f"Test Experiment {name}",
                    "description": "desc",
                    "test_type": "proportion",
                    "baseline_metric": 0.05,
                    "mde": 0.01,
                },
            )

        mock_load.side_effect = _make_sample
        await seed_sample_experiments(db)

    assert insert_count == 3, f"Expected 3 inserts on first call, got {insert_count}"

    # Second call: experiment found → skip all inserts
    insert_count = 0
    db.execute = AsyncMock(return_value=FakeResult2())
    db.add = MagicMock(side_effect=_add)

    with patch("app.data.sample_experiments.load_sample_experiment") as mock_load:
        mock_load.side_effect = _make_sample
        await seed_sample_experiments(db)

    assert insert_count == 0, f"Expected 0 inserts on second call, got {insert_count}"
