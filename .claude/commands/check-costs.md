Query the ai_interactions table and display a cost/usage report for the Claude API layer.

## Check DB availability

First, verify Docker is running:

```bash
docker compose ps db 2>&1 | grep -q "running\|Up" && echo "DB_UP" || echo "DB_DOWN"
```

If the result contains `DB_DOWN`, print:
```
DB not available — run: docker compose up -d
```
and stop.

## Run the queries

Run these three SQL queries via psql:

### Today

```bash
docker compose exec -T db psql -U axiom -d axiom -c "
SELECT
    interaction_type                                              AS function,
    COUNT(*)                                                      AS calls,
    COALESCE(SUM(input_tokens),  0)                               AS input_tokens,
    COALESCE(SUM(output_tokens), 0)                               AS output_tokens,
    ROUND(CAST(COALESCE(SUM(estimated_cost_usd), 0) AS numeric), 6) AS cost_usd,
    ROUND(CAST(AVG(duration_ms) AS numeric), 0)                   AS avg_latency_ms,
    CASE WHEN COUNT(*) = 0 THEN NULL
         ELSE ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'fallback_used') / COUNT(*), 1)
    END                                                           AS fallback_pct,
    MAX(estimated_cost_usd)                                       AS max_single_call_usd
FROM ai_interactions
WHERE created_at >= CURRENT_DATE
GROUP BY interaction_type
ORDER BY cost_usd DESC;
" 2>&1
```

### This week

```bash
docker compose exec -T db psql -U axiom -d axiom -c "
SELECT
    interaction_type                                              AS function,
    COUNT(*)                                                      AS calls,
    COALESCE(SUM(input_tokens),  0)                               AS input_tokens,
    COALESCE(SUM(output_tokens), 0)                               AS output_tokens,
    ROUND(CAST(COALESCE(SUM(estimated_cost_usd), 0) AS numeric), 6) AS cost_usd,
    ROUND(CAST(AVG(duration_ms) AS numeric), 0)                   AS avg_latency_ms,
    CASE WHEN COUNT(*) = 0 THEN NULL
         ELSE ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'fallback_used') / COUNT(*), 1)
    END                                                           AS fallback_pct
FROM ai_interactions
WHERE created_at >= DATE_TRUNC('week', CURRENT_DATE)
GROUP BY interaction_type
ORDER BY cost_usd DESC;
" 2>&1
```

### All time + most expensive single call

```bash
docker compose exec -T db psql -U axiom -d axiom -c "
SELECT
    interaction_type                                              AS function,
    COUNT(*)                                                      AS calls,
    COALESCE(SUM(input_tokens),  0)                               AS input_tokens,
    COALESCE(SUM(output_tokens), 0)                               AS output_tokens,
    ROUND(CAST(COALESCE(SUM(estimated_cost_usd), 0) AS numeric), 6) AS cost_usd,
    ROUND(CAST(AVG(duration_ms) AS numeric), 0)                   AS avg_latency_ms,
    CASE WHEN COUNT(*) = 0 THEN NULL
         ELSE ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'fallback_used') / COUNT(*), 1)
    END                                                           AS fallback_pct
FROM ai_interactions
GROUP BY interaction_type
ORDER BY cost_usd DESC;

SELECT
    id,
    interaction_type  AS function,
    input_tokens,
    output_tokens,
    ROUND(CAST(estimated_cost_usd AS numeric), 6) AS cost_usd,
    duration_ms,
    created_at
FROM ai_interactions
ORDER BY estimated_cost_usd DESC NULLS LAST
LIMIT 1;
" 2>&1
```

## Format the output

Present results as three clearly labelled sections:

```
════════════════════════════════════════════════════════
AXIOM CLAUDE API COST REPORT  (rates: $3/M input, $15/M output — Sonnet)
════════════════════════════════════════════════════════

TODAY
──────────────────────────────────────────────────────
Function       Calls  Input tok  Output tok  Cost USD  Avg ms  Fallback%
planner        ...
interpreter    ...
reporter       ...
──────────────────────────────────────────────────────
TOTAL          ...    ...        ...         $...

THIS WEEK
──────────────────────────────────────────────────────
(same columns)

ALL TIME
──────────────────────────────────────────────────────
(same columns)

Most expensive single call:
  ID:       <uuid>
  Function: <type>
  Tokens:   <input> in / <output> out
  Cost:     $<amount>
  Latency:  <ms> ms
  Time:     <created_at>
════════════════════════════════════════════════════════
```

- If a period has zero rows, print `(no calls recorded)` for that section.
- Costs use 4 decimal places (e.g. `$0.0315`).
- Fallback% shows percentage of calls where Claude was unavailable and the template fallback fired.
