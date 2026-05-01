#!/usr/bin/env bash
# Pre-bash hook: venv guard and pytest environment checks.
# Receives tool call JSON on stdin. Blocks only on clearly unsafe commands.

COMMAND=$(python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except Exception:
    print('')
" 2>/dev/null)

[[ -z "$COMMAND" ]] && exit 0

# Only act on Python-adjacent commands to avoid noise on git, ls, etc.
IS_PYTHON_CMD=false
for kw in python pytest black mypy isort ruff pip uvicorn; do
    if [[ "$COMMAND" == *"$kw"* ]]; then
        IS_PYTHON_CMD=true
        break
    fi
done

[[ "$IS_PYTHON_CMD" == false ]] && exit 0

PROJECT_ROOT="$(pwd)"
VENV="$PROJECT_ROOT/.venv"

# ── 1. Virtual environment guard ──────────────────────────────────────────────
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    if [[ -f "$VENV/bin/python" ]]; then
        echo "[pre-hook] ⚠ Virtual environment not active."
        echo "[pre-hook] Activate: source .venv/bin/activate"
        echo "[pre-hook] Or prefix commands with: .venv/bin/python / .venv/bin/pytest"
    fi
    # Non-blocking: warn and allow — don't interrupt normal work.
fi

# ── 2. Pytest + Docker check ──────────────────────────────────────────────────
if [[ "$COMMAND" == *"pytest"* ]]; then
    if [[ "$COMMAND" == *"integration"* || "$COMMAND" == *"tests/integration"* ]]; then
        DOCKER_RUNNING=false
        for sock in /var/run/docker.sock "$HOME/.docker/run/docker.sock"; do
            [[ -S "$sock" ]] && DOCKER_RUNNING=true && break
        done
        if [[ "$DOCKER_RUNNING" == false ]]; then
            echo "[pre-hook] ⚠ Integration tests require PostgreSQL via Docker."
            echo "[pre-hook] Docker is not running — these tests will fail."
            echo "[pre-hook] Run unit/stats tests instead: .venv/bin/pytest backend/tests/stats/ -v"
            # Non-blocking: inform but allow the command to run (might work with local Postgres).
        fi
    fi
fi

exit 0
