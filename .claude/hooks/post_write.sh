#!/usr/bin/env bash
# Post-write hook: runs quality checks scoped to the changed file.
# Receives tool call JSON on stdin. Non-blocking — warns, never blocks.

FILE_PATH=$(python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
" 2>/dev/null)

[[ -z "$FILE_PATH" ]] && exit 0

PROJECT_ROOT="$(pwd)"
VENV="$PROJECT_ROOT/.venv"

# Resolve tool binaries: prefer active venv, fall back to project venv.
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    BLACK="${VIRTUAL_ENV}/bin/black"
    ISORT="${VIRTUAL_ENV}/bin/isort"
    MYPY="${VIRTUAL_ENV}/bin/mypy"
    PYTEST="${VIRTUAL_ENV}/bin/python -m pytest"
elif [[ -f "$VENV/bin/python" ]]; then
    BLACK="$VENV/bin/black"
    ISORT="$VENV/bin/isort"
    MYPY="$VENV/bin/mypy"
    PYTEST="$VENV/bin/python -m pytest"
else
    echo "[hook] WARNING: No virtual environment found — quality checks skipped."
    echo "[hook] Create one: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt"
    exit 0
fi

cd "$PROJECT_ROOT"

HAS_ISSUES=false
STATS_FAILED=false

# ── 1. Stats module: run narrowest matching test file ──────────────────────────
if [[ "$FILE_PATH" == */backend/app/stats/*.py ]]; then
    MODULE=$(basename "$FILE_PATH" .py)
    TEST_FILE="backend/tests/stats/test_${MODULE}.py"

    echo ""
    echo "┌─ [stats-hook] ${MODULE}.py changed"

    if [[ -f "$TEST_FILE" ]]; then
        echo "│  pytest $TEST_FILE"
        if OUTPUT=$(PYTHONPATH="$PROJECT_ROOT/backend" $PYTEST "$TEST_FILE" --tb=short -q 2>&1); then
            SUMMARY=$(echo "$OUTPUT" | grep -E "passed|failed|error" | tail -1)
            echo "│  ✓ $SUMMARY"
        else
            SUMMARY=$(echo "$OUTPUT" | grep -E "passed|failed|error" | tail -1)
            echo "│  ✗ $SUMMARY"
            echo "$OUTPUT" | grep -E "FAILED|ERROR|assert" | head -10 | sed 's/^/│    /'
            STATS_FAILED=true
        fi
    else
        echo "│  pytest backend/tests/stats/ (no test_${MODULE}.py found)"
        if OUTPUT=$(PYTHONPATH="$PROJECT_ROOT/backend" $PYTEST backend/tests/stats/ --tb=short -q 2>&1); then
            SUMMARY=$(echo "$OUTPUT" | grep -E "passed|failed|error" | tail -1)
            echo "│  ✓ $SUMMARY"
        else
            SUMMARY=$(echo "$OUTPUT" | grep -E "passed|failed|error" | tail -1)
            echo "│  ✗ $SUMMARY"
            echo "$OUTPUT" | grep -E "FAILED|ERROR|assert" | head -10 | sed 's/^/│    /'
            STATS_FAILED=true
        fi
    fi

    echo "└──"
fi

# ── 2. Mypy: backend app Python files (warning, non-blocking) ─────────────────
if [[ "$FILE_PATH" == *.py && "$FILE_PATH" == */backend/app/* ]]; then
    echo ""
    echo "┌─ [mypy-hook] $(basename "$FILE_PATH")"

    if OUTPUT=$($MYPY "$FILE_PATH" \
        --ignore-missing-imports \
        --no-error-summary \
        --python-version 3.11 \
        --follow-imports=silent 2>&1); then
        echo "│  ✓ No type errors"
    else
        ERRORS=$(echo "$OUTPUT" | grep -c "error:" || true)
        if [[ "$ERRORS" -gt 0 ]]; then
            echo "│  ⚠ ${ERRORS} error(s) — fix before committing"
            echo "$OUTPUT" | grep "error:" | head -6 | sed 's/^/│    /'
            HAS_ISSUES=true
        else
            # Non-zero exit but no error lines (e.g. config notes) — treat as clean.
            echo "│  ✓ No type errors"
        fi
    fi

    echo "└──"
fi

# ── 3. Black + isort: any .py file ────────────────────────────────────────────
if [[ "$FILE_PATH" == *.py ]]; then
    echo ""
    echo "┌─ [format-hook] $(basename "$FILE_PATH")"

    if $BLACK --check --quiet "$FILE_PATH" 2>/dev/null; then
        echo "│  ✓ black: formatted correctly"
    else
        echo "│  ⚠ black: would reformat  →  black $(basename "$FILE_PATH")"
        HAS_ISSUES=true
    fi

    if $ISORT --check-only --quiet "$FILE_PATH" 2>/dev/null; then
        echo "│  ✓ isort: imports ordered"
    else
        echo "│  ⚠ isort: imports out of order  →  isort $(basename "$FILE_PATH")"
        HAS_ISSUES=true
    fi

    echo "└──"
fi

# ── 4. Docs markdown lint (informational only) ────────────────────────────────
if [[ "$FILE_PATH" == */docs/*.md ]]; then
    echo ""
    echo "┌─ [docs-hook] $(basename "$FILE_PATH")"

    if command -v markdownlint &>/dev/null; then
        if OUTPUT=$(markdownlint "$FILE_PATH" 2>&1); then
            echo "│  ✓ markdownlint: OK"
        else
            echo "│  ℹ markdownlint (informational):"
            echo "$OUTPUT" | head -5 | sed 's/^/│    /'
        fi
    else
        echo "│  ℹ markdownlint not installed — skipping (npm i -g markdownlint-cli to enable)"
    fi

    echo "└──"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
if [[ "$STATS_FAILED" == true ]]; then
    echo "[hook] ✗ STATS TESTS FAILED — fix before proceeding (100% coverage required)"
    exit 1
fi

if [[ "$HAS_ISSUES" == true ]]; then
    echo "[hook] ⚠ Formatting/type issues found — fix before committing."
fi

exit 0
