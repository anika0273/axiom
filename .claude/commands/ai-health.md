Test all three AI intelligence functions with minimal prompts and report latency. Total should complete in under 90 seconds.

## Setup — verify the server is running

```bash
curl -s --max-time 5 http://localhost:8000/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('SERVER_UP' if d.get('status')=='healthy' or d.get('ok') else 'SERVER_DOWN')" 2>/dev/null || echo "SERVER_DOWN"
```

If `SERVER_DOWN`, print:
```
Server not running. Start with:
  PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
and stop.

---

## Test 1 — Planner

Time the following request:

```bash
START=$(python3 -c "import time; print(time.time())")
curl -s -X POST http://localhost:8000/api/v1/intelligence/plan \
  -H "Content-Type: application/json" \
  -d '{"description": "Test a simple button color change. CVR=5%, traffic=100/day"}' \
  2>&1
END=$(python3 -c "import time; print(time.time())")
echo "LATENCY_MS: $(python3 -c "print(round(($END - $START)*1000))")"
```

A successful planner response contains either `"hypotheses"` or `"clarifying_questions"` in the JSON. Check which one and report accordingly.

---

## Test 2 — Interpreter (SSE stream)

Load the pre-computed SaaS result from the seeded database:

```bash
# Get the experiment ID for the SaaS trial experiment
docker compose exec -T db psql -U axiom -d axiom -c "SELECT id FROM experiments WHERE name ILIKE '%saas%' OR name ILIKE '%trial%' LIMIT 1;" 2>&1
```

If DB is unavailable, print `DB not available — skipping interpreter test (run: docker compose up -d)` and skip to Test 3.

If an experiment ID is found, time the SSE stream:

```bash
START=$(python3 -c "import time; print(time.time())")
curl -s --max-time 60 -N \
  http://localhost:8000/api/v1/intelligence/experiments/<ID>/interpret \
  | head -c 500
END=$(python3 -c "import time; print(time.time())")
echo "LATENCY_MS: $(python3 -c "print(round(($END - $START)*1000))")"
```

A successful response starts with `data:` SSE lines. Check if `[FALLBACK]` appears in the stream (means Claude was unavailable, template fired instead).

---

## Test 3 — Reporter

Using the same experiment ID (or skip if DB unavailable):

```bash
START=$(python3 -c "import time; print(time.time())")
curl -s -X POST http://localhost:8000/api/v1/intelligence/experiments/<ID>/report \
  -H "Content-Type: application/json" \
  -d '{"format": "markdown"}' \
  2>&1 | python3 -c "import sys,json; d=json.load(sys.stdin); print('confidence:', d.get('data',{}).get('confidence_level','?'), '| sections:', len(d.get('data',{}).get('sections',[])))"
END=$(python3 -c "import time; print(time.time())")
echo "LATENCY_MS: $(python3 -c "print(round(($END - $START)*1000))")"
```

A successful reporter response has `"data"` with `"sections"` (list of 8).

---

## Final report

```
════════════════════════════════════════
AI HEALTH CHECK  —  $(date)
────────────────────────────────────────
Function      Status    Latency   Notes
────────────────────────────────────────
planner       PASS/FAIL  XXXXms   [clarifying | full plan | FALLBACK]
interpreter   PASS/FAIL  XXXXms   [streaming | FALLBACK | skipped]
reporter      PASS/FAIL  XXXXms   [confidence=X | skipped]
────────────────────────────────────────
Overall: PASS / PARTIAL / FAIL
Total elapsed: Xs  (target: < 90s)
════════════════════════════════════════
```

- PASS: function responded with valid output within the expected structure
- FAIL: HTTP error, timeout, or JSON parse error
- PARTIAL: some tests skipped due to DB unavailability
- If any function shows FAIL, print the raw error response below the table
