"""Live demo of the experiment planner against the real Claude API.

Usage:
    PYTHONPATH=backend python scripts/demo_planner.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.intelligence.planner import plan_experiment


async def run_demo(label: str, description: str, context: dict | None = None) -> None:
    print(f"\n{'=' * 70}")
    print(f"DEMO: {label}")
    print(f"{'=' * 70}")
    print(f"INPUT: {description[:120]}{'...' if len(description) > 120 else ''}")
    if context:
        print(f"CONTEXT: {json.dumps(context)}")
    print()

    try:
        result = await plan_experiment(description=description, context=context, db=None)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return

    if result.needs_clarification:
        print(f"STATUS: needs_clarification=True")
        print(f"CONFIDENCE: {result.confidence}")
        print(f"REASONING: {result.confidence_reasoning}")
        print(f"\nCLARIFYING QUESTIONS ({len(result.clarifying_questions)}):")
        for i, q in enumerate(result.clarifying_questions, 1):
            print(f"  {i}. {q}")
        print(f"\nPROMPT_VERSION: {result.prompt_version}")
        return

    plan = result.plan
    assert plan is not None

    print(f"STATUS: plan generated")
    print(f"CONFIDENCE: {result.confidence}")
    print(f"REASONING: {result.confidence_reasoning}")
    print()
    print(f"EXPERIMENT NAME  : {plan.experiment_name}")
    print(f"HYPOTHESIS       : {plan.hypothesis}")
    print()
    print(f"PRIMARY METRIC   : {plan.primary_metric.name}")
    print(f"  type           : {plan.primary_metric.type}")
    print(f"  baseline       : {plan.primary_metric.baseline}")
    print(f"RECOMMENDED MDE  : {plan.recommended_mde}")
    print()

    if result.stats_engine_verification:
        v = result.stats_engine_verification
        print(f"STATS ENGINE VERIFICATION:")
        print(f"  sample_size_per_group : {plan.sample_size_per_group}")
        print(f"  total_sample_size     : {v.total_sample_size}")
        print(f"  cohens_d              : {v.cohens_d:.4f}")
        print(f"  method                : {v.method_used}")
    else:
        print(f"STATS ENGINE VERIFICATION: skipped (missing baseline/MDE)")

    print()
    if plan.estimated_runtime_days is not None:
        print(f"ESTIMATED RUNTIME: {plan.estimated_runtime_days:.1f} days")
    else:
        print(f"ESTIMATED RUNTIME: unknown (daily traffic not provided)")

    print(f"\nSTATISTICAL CONFIG:")
    cfg = plan.statistical_config
    print(f"  alpha               : {cfg.alpha}")
    print(f"  power               : {cfg.power}")
    print(f"  test_type           : {cfg.test_type}")
    print(f"  sequential_testing  : {cfg.sequential_testing}")
    print(f"  cuped_applicable    : {cfg.cuped_applicable}")

    print(f"\nSECONDARY METRICS  : {plan.secondary_metrics}")
    print(f"GUARDRAIL METRICS  : {plan.guardrail_metrics}")

    print(f"\nRISKS ({len(plan.risks)}):")
    for i, risk in enumerate(plan.risks, 1):
        print(f"  {i}. {risk}")

    print(f"\nPLANNER NOTES  : {plan.planner_notes}")
    print(f"PROMPT_VERSION : {result.prompt_version}")


async def main() -> None:
    # ── Demo 1: checkout button ───────────────────────────────────────────────
    await run_demo(
        label="Checkout Button Color Test (well-specified)",
        description=(
            "We want to test if changing our checkout button from green to orange "
            "increases purchases. We get about 500 orders per day and our current "
            "conversion rate is about 3%."
        ),
        context={"daily_traffic": 500},
    )

    # ── Demo 2: vague input ───────────────────────────────────────────────────
    await run_demo(
        label="Vague Input — should return clarifying questions",
        description="Test my app",
    )

    # ── Demo 3: enterprise pricing page ──────────────────────────────────────
    await run_demo(
        label="Enterprise Pricing Page (fully specified)",
        description=(
            "We want to A/B test our pricing page for enterprise customers. "
            "Current trial-to-paid rate is 15%. We have 200 signups/day. "
            "We want to detect a 3pp improvement. We care about not hurting "
            "time-to-convert as a guardrail."
        ),
        context={"daily_traffic": 200},
    )


if __name__ == "__main__":
    asyncio.run(main())
