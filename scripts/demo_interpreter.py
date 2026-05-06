"""Live demo of the experiment result interpreter against the real Claude API.

Loads a pre-computed sample experiment, hydrates the interpreter models from
its JSON, and streams the Claude interpretation word-by-word to the terminal.

Usage:
    PYTHONPATH=backend python scripts/demo_interpreter.py [ecommerce_checkout|saas_trial|marketplace_fee]
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

# Allow running from the project root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.data.sample_experiments import load_sample_experiment
from app.intelligence.interpreter import (
    build_fallback_interpretation,
    interpret_results,
    parse_ml_from_json,
    parse_stats_from_json,
)


def _divider(char: str = "─", width: int = 70) -> str:
    return char * width


async def run_demo(experiment_name: str) -> None:
    print(_divider("="))
    print(f"  AXIOM INTERPRETER DEMO — {experiment_name}")
    print(_divider("="))

    sample = load_sample_experiment(experiment_name)
    meta = sample.metadata

    print(f"\n  Experiment : {meta['name']}")
    print(f"  Description: {meta['description'][:90]}...")
    print(f"  N users    : {meta['n_users']:,}  |  N days: {meta['n_days']}")
    print(f"  True ATE   : {meta['true_ate']:+.4f}  |  Expected verdict: {meta['expected_verdict']}")

    precomputed = sample.precomputed_result
    stats = parse_stats_from_json(precomputed)
    ml = parse_ml_from_json(precomputed)

    print(f"\n  Stats  → significant={stats.is_significant}, lift={stats.lift_pct:+.4f}%, p={stats.p_value:.4f}")
    print(f"  ML     → verdict={ml.overall_verdict}, can_trust={ml.can_trust_results}")
    if ml.hte_top_modifier:
        clean_mod = ml.hte_top_modifier.replace("_x_treat", "")
        print(f"  HTE    → top modifier: {clean_mod}, ATE={ml.hte_ate:+.4f}")
    if ml.responsive_segments is not None:
        print(f"  Segs   → responsive: {ml.responsive_segments}")

    print(f"\n{_divider()}")
    print("  STREAMING INTERPRETATION (Claude → word by word)")
    print(_divider())
    print()

    t0 = time.perf_counter()
    chunk_count = 0
    total_chars = 0

    try:
        async for chunk in interpret_results(
            stats_result=stats,
            ml_result=ml,
            experiment_name=meta["name"],
            daily_traffic=None,
        ):
            print(chunk, end="", flush=True)
            chunk_count += 1
            total_chars += len(chunk)

        elapsed = time.perf_counter() - t0
        print(f"\n\n{_divider()}")
        print(
            f"  Stream complete in {elapsed:.1f}s — "
            f"{chunk_count} chunks, {total_chars} chars"
        )

    except Exception as exc:
        elapsed = time.perf_counter() - t0
        print(f"\n\n  Stream failed after {elapsed:.1f}s: {type(exc).__name__}: {exc}")
        print(f"\n{_divider()}")
        print("  FALLBACK INTERPRETATION (template-based, no Claude)")
        print(_divider())
        print()
        print(build_fallback_interpretation(stats, ml))

    print(_divider("="))


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "saas_trial"
    valid = ("ecommerce_checkout", "saas_trial", "marketplace_fee")
    if name not in valid:
        print(f"Unknown experiment '{name}'. Choose from: {', '.join(valid)}")
        sys.exit(1)
    asyncio.run(run_demo(name))
