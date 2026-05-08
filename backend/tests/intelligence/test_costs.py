"""Unit tests for intelligence.costs — cost estimation helpers."""
from __future__ import annotations

import pytest

from app.intelligence.costs import estimate_cost


class TestEstimateCost:
    def test_sonnet_rates_applied(self) -> None:
        # $3/M input, $15/M output for claude-sonnet-4-*
        cost = estimate_cost(1_000_000, 0, model="claude-sonnet-4-6")
        assert pytest.approx(cost, rel=1e-6) == 3.0

    def test_opus_rates_applied(self) -> None:
        # $15/M input, $75/M output for claude-opus-4-*
        cost = estimate_cost(1_000_000, 0, model="claude-opus-4-7")
        assert pytest.approx(cost, rel=1e-6) == 15.0

    def test_haiku_rates_applied(self) -> None:
        # $0.80/M input, $4/M output for claude-haiku-4-*
        cost = estimate_cost(1_000_000, 0, model="claude-haiku-4-5")
        assert pytest.approx(cost, rel=1e-6) == 0.80

    def test_output_tokens_billed_separately(self) -> None:
        # Sonnet: $3/M in + $15/M out
        cost = estimate_cost(0, 1_000_000, model="claude-sonnet-4-6")
        assert pytest.approx(cost, rel=1e-6) == 15.0

    def test_combined_input_and_output(self) -> None:
        cost = estimate_cost(1_000, 500, model="claude-sonnet-4-6")
        # (1000 * 3 + 500 * 15) / 1_000_000 = 0.003 + 0.0075 = 0.0105
        assert pytest.approx(cost, rel=1e-4) == 0.0105

    def test_zero_tokens_returns_zero(self) -> None:
        assert estimate_cost(0, 0) == 0.0

    def test_unknown_model_falls_back_to_sonnet_default(self) -> None:
        cost_unknown = estimate_cost(1_000, 500, model="claude-unknown-future-99")
        cost_sonnet = estimate_cost(1_000, 500, model="claude-sonnet-4-6")
        assert pytest.approx(cost_unknown, rel=1e-6) == cost_sonnet

    def test_legacy_sonnet_35_prefix_matched(self) -> None:
        cost = estimate_cost(1_000_000, 0, model="claude-3-5-sonnet-20241022")
        assert pytest.approx(cost, rel=1e-6) == 3.0

    def test_default_model_is_sonnet(self) -> None:
        cost_default = estimate_cost(1_000, 500)
        cost_explicit = estimate_cost(1_000, 500, model="claude-sonnet-4")
        assert pytest.approx(cost_default, rel=1e-6) == cost_explicit

    def test_small_call_returns_nonzero(self) -> None:
        cost = estimate_cost(100, 50, model="claude-sonnet-4-6")
        assert cost > 0
        assert cost < 0.01  # a 150-token call should cost less than a cent
