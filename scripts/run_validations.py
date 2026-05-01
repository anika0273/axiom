#!/usr/bin/env python3
"""Run the Axiom stats engine validation suite and generate the report.

Usage
-----
    python scripts/run_validations.py            # run all validations
    python scripts/run_validations.py -k seq     # run matching scenarios only
    python scripts/run_validations.py -x         # stop on first failure

The validation report is written to docs/validation_report.md automatically
by the pytest plugin in backend/tests/validation/conftest.py.

Exit code
---------
0  all validations passed
1  one or more validations failed
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
VALIDATION_DIR = ROOT / "backend" / "tests" / "validation"
REPORT_PATH = ROOT / "docs" / "validation_report.md"


def main() -> int:
    extra_args = sys.argv[1:]

    cmd = [
        sys.executable, "-m", "pytest",
        str(VALIDATION_DIR),
        "-v",
        "--tb=short",
        "--no-header",
        *extra_args,
    ]

    print("=" * 72)
    print("Axiom Stats Engine — Validation Suite")
    print("=" * 72)
    print(f"Running: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=str(ROOT))

    if REPORT_PATH.exists():
        print(f"\nReport: {REPORT_PATH}")
    else:
        print("\n[warning] Report not generated — no validation tests may have run.")

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
