Run AI integration tests with verbose output and timing, then summarise Claude API call cost from the database.

## Step 1 — Run integration tests

```bash
cd /Users/owner/Desktop/Test_claude && PYTHONPATH=backend .venv/bin/python -m pytest -m integration backend/tests/integration/ -v --tb=short --durations=10 2>&1
```

Report for each test:
- Name, PASSED / FAILED / ERROR status, and duration in seconds
- For failures: the full assertion error and the most relevant traceback lines

## Step 2 — Summarise Claude API calls from the database

After the tests finish, run:

```bash
docker compose exec -T db psql -U axiom -d axiom -c "
SELECT
    interaction_type                          AS function,
    COUNT(*)                                  AS calls,
    COALESCE(SUM(input_tokens), 0)            AS input_tokens,
    COALESCE(SUM(output_tokens), 0)           AS output_tokens,
    ROUND(CAST(COALESCE(SUM(estimated_cost_usd), 0) AS numeric), 6) AS cost_usd,
    ROUND(CAST(AVG(duration_ms) AS numeric), 0) AS avg_latency_ms
FROM ai_interactions
WHERE created_at >= NOW() - INTERVAL '1 hour'
GROUP BY interaction_type
ORDER BY calls DESC;
" 2>&1
```

If the database is not running, print:
```
DB not available — run: docker compose up -d
Skipping cost summary.
```

## Report format

Print a summary block at the end:

```
════════════════════════════════════════
AI INTEGRATION TEST SUMMARY
────────────────────────────────────────
Tests run:    <N>
Passed:       <N>
Failed:       <N>
Skipped:      <N>
Total time:   <Xs>

CLAUDE API CALLS (last 1 hour)
────────────────────────────────────────
Function       Calls  Input tok  Output tok  Cost USD  Avg ms
planner        ...
interpreter    ...
reporter       ...
────────────────────────────────────────
TOTAL          ...    ...        ...         $...      ...
════════════════════════════════════════
```
