"""Validation record model, shared record list, and markdown report writer.

Tests import ``record`` to add results; conftest calls ``write_report`` at
session end.  The module-level ``_val_records`` list is the shared store.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclasses.dataclass
class ValidationRecord:
    """One row in the validation report."""

    module: str  # e.g. "sample_size"
    scenario: str  # human label, e.g. "S1: canonical 5%→6%"
    expected: str  # formatted expected value
    observed: str  # formatted observed value
    delta: str  # formatted discrepancy
    tolerance: str  # stated tolerance
    passed: bool
    likely_cause: str = ""  # filled only on failure
    notes: str = ""


# ---------------------------------------------------------------------------
# Shared store
# ---------------------------------------------------------------------------

_val_records: list[ValidationRecord] = []


def record(
    module: str,
    scenario: str,
    expected: str,
    observed: str,
    delta: str,
    tolerance: str,
    passed: bool,
    likely_cause: str = "",
    notes: str = "",
) -> None:
    """Append a single validation result to the shared store."""
    _val_records.append(
        ValidationRecord(
            module=module,
            scenario=scenario,
            expected=expected,
            observed=observed,
            delta=delta,
            tolerance=tolerance,
            passed=passed,
            likely_cause=likely_cause,
            notes=notes,
        )
    )


# ---------------------------------------------------------------------------
# Module display names (ordered)
# ---------------------------------------------------------------------------

_MODULE_NAMES: dict[str, str] = {
    "sample_size": "1. Sample Size",
    "proportion_test": "2. Two-Proportion Z-Test",
    "mean_test": "3. Mean Test (Welch t-test)",
    "ratio_metric": "4. Ratio Metric (Delta Method)",
    "cuped": "5. CUPED Variance Reduction",
    "sequential": "6. Sequential / O'Brien-Fleming",
    "corrections": "7. Multiple Comparison Corrections",
    "engine_integration": "8. Engine Integration",
}


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------


def write_report(records: list[ValidationRecord], output_path: Path) -> None:
    """Write a markdown validation report to *output_path*."""
    modules = list(dict.fromkeys(r.module for r in records))  # preserve insertion order

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(records)
    passed = sum(1 for r in records if r.passed)
    failed = total - passed

    lines: list[str] = [
        "# Axiom Stats Engine — Validation Report",
        "",
        f"> Generated: {now}  ",
        f"> Total: {total} scenarios | Passed: {passed} | Failed: {failed}",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Module | Total | Passed | Failed |",
        "|--------|------:|-------:|-------:|",
    ]

    for mod in modules:
        recs = [r for r in records if r.module == mod]
        n_pass = sum(1 for r in recs if r.passed)
        n_fail = len(recs) - n_pass
        icon = "✅" if n_fail == 0 else "❌"
        name = _MODULE_NAMES.get(mod, mod)
        lines.append(f"| {icon} {name} | {len(recs)} | {n_pass} | {n_fail} |")

    lines += [
        f"| **Total** | **{total}** | **{passed}** | **{failed}** |",
        "",
        "---",
        "",
    ]

    # Per-module tables
    for mod in modules:
        name = _MODULE_NAMES.get(mod, mod)
        recs = [r for r in records if r.module == mod]
        lines += [
            f"## {name}",
            "",
            "| Scenario | Expected | Observed | Delta | Tolerance | Status | Likely Cause |",
            "|----------|----------|----------|-------|-----------|:------:|:-------------|",
        ]
        for r in recs:
            icon = "✅ PASS" if r.passed else "❌ FAIL"
            cause = r.likely_cause if r.likely_cause else "—"
            lines.append(
                f"| {r.scenario} | `{r.expected}` | `{r.observed}` "
                f"| {r.delta} | {r.tolerance} | {icon} | {cause} |"
            )
        lines.append("")

    # Failure detail section
    failures = [r for r in records if not r.passed]
    if failures:
        lines += ["---", "", "## ❌ Failed Scenarios — Detail", ""]
        for r in failures:
            lines += [
                f"### {r.module}: {r.scenario}",
                f"- **Expected**: `{r.expected}`",
                f"- **Observed**: `{r.observed}`",
                f"- **Delta**: {r.delta} (tolerance: {r.tolerance})",
                f"- **Likely cause**: {r.likely_cause or 'Not specified'}",
                f"- **Notes**: {r.notes or 'None'}",
                "",
            ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n[validation] Report written → {output_path}")
