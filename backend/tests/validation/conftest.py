"""Pytest plugin for the validation suite.

Hooks into ``pytest_sessionfinish`` to write docs/validation_report.md
automatically whenever any test in this directory runs.
"""
from __future__ import annotations

from pathlib import Path

# Report output path relative to project root
_REPORT_PATH = Path(__file__).parents[3] / "docs" / "validation_report.md"


def pytest_sessionfinish(session: object, exitstatus: object) -> None:  # noqa: ARG001
    from tests.validation._report import _val_records, write_report  # noqa: PLC0415

    if _val_records:
        write_report(_val_records, _REPORT_PATH)
