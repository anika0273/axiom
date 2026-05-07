"""Cost estimation helpers for Claude API calls.

Rates are hard-coded here (not in config) because they are pricing constants
tied to model versions, not deployment configuration. Update the RATES dict
when Anthropic changes pricing — bump the version suffix on affected models.
"""

from __future__ import annotations

# USD per million tokens, keyed by model name prefix.
# Partial name match: e.g. "claude-sonnet-4" matches "claude-sonnet-4-6".
_RATES: dict[str, tuple[float, float]] = {
    # (input_per_million, output_per_million)
    "claude-opus-4": (15.00, 75.00),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-haiku-4": (0.80, 4.00),
    # Legacy fallback
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-opus": (15.00, 75.00),
    "claude-3-haiku": (0.25, 1.25),
}

_DEFAULT_RATES: tuple[float, float] = (3.00, 15.00)  # assume Sonnet if unknown


def _get_rates(model: str) -> tuple[float, float]:
    """Return (input_usd_per_million, output_usd_per_million) for *model*."""
    for prefix, rates in _RATES.items():
        if model.startswith(prefix):
            return rates
    return _DEFAULT_RATES


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str = "claude-sonnet-4",
) -> float:
    """Estimate Claude API cost in USD for a single call.

    Args:
        input_tokens: Number of input tokens consumed (from response.usage).
        output_tokens: Number of output tokens generated (from response.usage).
        model: Model ID string. Matched by prefix against the known rates table.
            Defaults to "claude-sonnet-4" ($3.00/M in, $15.00/M out).

    Returns:
        Estimated cost in USD as a float.
    """
    input_rate, output_rate = _get_rates(model)
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
