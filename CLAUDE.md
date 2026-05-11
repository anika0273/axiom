# Axiom — AI-Powered A/B Testing Platform

## Build Status — Phase 4 Complete ✓ (2026-05-10)

### Phase 1 — Stats Engine & API
| Component | Status | Detail |
|---|---|---|
| Stats engine | ✓ 430/430 tests passing | `backend/app/stats/` — z-test, t-test, CUPED, sequential, corrections, power |
| FastAPI backend | ✓ 28/28 API tests passing | `backend/app/api/v1/` — stats endpoints, middleware, rate limiting |
| Docker + PostgreSQL | ✓ Both containers healthy | `docker-compose.yml` — multi-stage build, non-root user, healthchecks |
| Database schema | ✓ Migration applied | 4 tables: `experiments`, `experiment_results`, `experiment_metrics`, `ai_interactions` |
| Sample data | ✓ Seeds loaded | `backend/migrations/seeds.py` — one complete experiment with result, metrics, AI log |
| Stats coverage | 96% line coverage | Gaps: power.py edge branches (86%), engine.py error paths (96%) |

### Phase 2 — ML Engine (complete 2026-05-05)
| Component | Status | Detail |
|---|---|---|
| ML modules | ✓ 5 modules | `backend/app/ml/` — hte, segments, anomaly, novelty, engine |
| ML API endpoints | ✓ 93% coverage | `backend/app/api/v1/ml.py` — analyse, validate, hte, segments, novelty |
| Sample datasets | ✓ 3 datasets | `backend/app/data/samples/` — ecommerce, saas, marketplace (pre-computed) |
| ML test suite | ✓ 751/751 passing | `backend/tests/ml/` — unit tests for all five modules |
| Combined coverage | 85% overall | `backend/app/ml/` all modules ≥ 93% |
| ML docs | ✓ Complete | `docs/ml/EXPLAINERS.md`, `docs/ml/DECISIONS.md` |
| Smoke test | ✓ Passing | `scripts/smoke_test_ml.py` — end-to-end regression check |

### Phase 4 — Professional React Frontend (complete 2026-05-10)
| Component | Status | Detail |
|---|---|---|
| Pages | ✓ 9/9 E2E journeys passing | Home, ExperimentList, NewExperiment (wizard), ExperimentResults, StakeholderReport, Demo, DemoExperimentResults, NotFound, Error |
| Design system | ✓ Complete | CSS variables, Syne headings, DM Mono data, 6px card radius, focus-visible rings |
| Charts | ✓ Recharts | `components/charts/` — MetricComparisonChart, SequentialChart; wrapped with React.memo |
| Streaming UI | ✓ SSE + simulated progress | `useStreamingInterpretation` (EventSource), `useStreamingReport` (POST + interval) |
| Demo mode | ✓ Zero API calls | Pre-computed local JSON; 3 datasets (ecommerce, saas, marketplace) |
| Performance | ✓ Route code-splitting | All pages lazy-loaded via `React.lazy` + `Suspense`; fonts preloaded in index.html |
| Frontend docs | ✓ Complete | `docs/frontend/ARCHITECTURE.md` — hierarchy, state, data fetching, streaming, tokens |

### Phase 3 — Claude AI Intelligence Layer (complete 2026-05-06)
| Component | Status | Detail |
|---|---|---|
| Intelligence modules | ✓ 6 modules | `backend/app/intelligence/` — planner, interpreter, reporter, guardrails, fallbacks, costs |
| AI API endpoints | ✓ Wired | `backend/app/api/v1/intelligence.py` — plan, interpret (SSE), report, usage |
| Intelligence test suite | ✓ 894/894 passing | `backend/tests/intelligence/` + `backend/tests/integration/test_intelligence.py` |
| Intelligence coverage | 90% overall | All modules ≥ 80%; `costs.py` 100%, `fallbacks.py` 100% |
| Phase 3 docs | ✓ Complete | `docs/intelligence/EXPLAINERS.md`, `docs/intelligence/DECISIONS.md` |
| Checkpoint report | ✓ Complete | `docs/intelligence/PHASE3_CHECKPOINT.md` — all 7 checkpoints PASS |

### Intelligence Modules (`backend/app/intelligence/`)
| Module | What it does |
|---|---|
| `planner.py` | NL description → structured `ExperimentPlan` via tool_use; stats engine verifies sample size |
| `interpreter.py` | Streams plain-English result interpretation; grounding validator prevents lift hallucination |
| `reporter.py` | 8-section stakeholder report via tool_use; Section 8 always programmatic |
| `guardrails.py` | `InputGuardrail` (injection detection), `OutputValidator` (auto-fix SHIP/nonsig), `RateLimiter`, `ClaudeCallWrapper` |
| `fallbacks.py` | Template-based responses for all 3 functions when Claude API is unavailable |
| `costs.py` | Per-model token cost estimation; rates table keyed by model prefix |

**Run command:** `PYTHONPATH=backend uvicorn app.main:app --host 0.0.0.0 --port 8000`
**Full stack:** `docker compose up -d` (requires `.env` from `.env.example`)
**Tests (all):** `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/ --cov=backend/app --cov-report=term-missing -q`
**Tests (intelligence only):** `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/intelligence/ -q`
**Tests (ML only):** `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/ml/ -q`
**Tests (stats only):** `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/stats/ backend/tests/unit/ -q`
**AI health check:** `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/intelligence/ -q`
**Cost monitoring:** `curl http://localhost:8000/api/v1/intelligence/usage`
**Smoke test:** `PYTHONPATH=backend python scripts/smoke_test_ml.py`
**Migration:** `docker compose exec backend alembic upgrade head`

---

## What Axiom Does

Axiom is an intelligent experimentation platform that lets teams design, run, and analyze A/B tests with statistical rigor and ML-assisted insights. It handles experiment lifecycle management (creation, audience assignment, traffic splitting), computes frequentist and Bayesian statistics on results, and uses Claude to generate plain-language summaries and recommendations. A React dashboard surfaces live experiment status, metric charts, and AI-generated reports.

---

## Project Goals and Non-Goals

### Goals
- Provide a self-hosted, API-first experimentation platform that can be integrated into any product.
- Guarantee statistically valid experiment results by enforcing correct assignment, no peeking, and sample-ratio mismatch detection.
- Surface AI-assisted insights (summaries, recommendations) that accelerate decision-making without replacing analyst judgment.
- Support both frequentist (z-test, t-test, chi-squared) and Bayesian (Beta-Binomial) analysis paths for the same experiment.

### Non-Goals
- Axiom does not implement its own feature-flag SDK or client-side event tracking library — it consumes events posted to its API by the caller's existing instrumentation.
- Axiom does not replace a data warehouse; it is an analysis layer, not a storage layer for raw event streams.
- Axiom does not make autonomous product decisions; all AI-generated recommendations require human approval before action.
- Multi-armed bandit / online learning traffic allocation is out of scope for v1.

---

## Source of Truth

| Concern | Canonical location |
|---|---|
| Experiment assignment logic | `backend/app/services/assignment_service.py` — nowhere else |
| Statistical test implementations | `backend/app/stats/` — services call these, never reimplement inline |
| Metric definitions and aggregation | `backend/app/services/metric_service.py` |
| Claude prompt templates | `backend/app/ai/prompts.py` — never inline elsewhere |
| Environment config | `backend/app/core/config.py` — never read `os.environ` outside this file |
| API response shapes | `backend/app/schemas/` Pydantic models — the schema is the contract |

If business logic appears in more than one place, that is a bug. Consolidate to the canonical location.

---

## Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python 3.11) |
| Database | PostgreSQL 15 via SQLAlchemy 2.x (async) |
| Statistics | scipy, statsmodels, numpy |
| ML | scikit-learn, XGBoost, SHAP |
| AI | Anthropic SDK (Claude) |
| Frontend | React 18 + Vite + Tailwind CSS + Recharts |
| Deployment | Docker + GitHub Actions CI + Railway |

---

## Folder Structure

```
axiom/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # FastAPI route handlers (one file per resource)
│   │   ├── core/               # Config, security, logging, lifespan hooks
│   │   ├── db/                 # SQLAlchemy engine, session factory, migrations (Alembic)
│   │   ├── models/             # ORM table definitions
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── services/           # Business logic (no HTTP concerns)
│   │   ├── stats/              # Statistical test implementations
│   │   ├── ml/                 # ML models for predictive lift, CUPED, etc.
│   │   └── ai/                 # Claude integration — prompts, summarisation
│   └── tests/
│       ├── unit/               # Pure-function tests (stats, ML, services)
│       └── integration/        # DB + API endpoint tests
├── frontend/
│   ├── src/
│   │   ├── components/         # Reusable UI components
│   │   ├── pages/              # Route-level page components
│   │   ├── hooks/              # Custom React hooks
│   │   ├── utils/              # Pure helper functions
│   │   ├── services/           # API client functions (axios/fetch wrappers)
│   │   └── store/              # Global state (Zustand or Context)
│   └── public/
├── infrastructure/
│   ├── docker/                 # Dockerfiles for backend and frontend
│   └── github/workflows/       # CI/CD GitHub Actions
├── docs/                       # Architecture docs, ADRs, API reference
├── scripts/                    # Dev-ops helpers (seed DB, run migrations, etc.)
├── .env.example
├── .gitignore
├── docker-compose.yml
├── requirements.txt
└── CLAUDE.md
```

---

## Coding Conventions

### Python (backend)
- **Type hints on every function signature** — parameters and return type, no exceptions.
- **Docstrings on every public function and class** — one-line summary + Args/Returns sections for non-trivial functions.
- **pytest for all statistical and ML functions** — every function in `stats/` and `ml/` must have a corresponding test in `tests/unit/`.
- Use `async def` for all FastAPI route handlers and any function that touches the database.
- SQLAlchemy models live in `models/`; Pydantic schemas live in `schemas/` — never mix them.
- Services in `services/` own business logic; they must not import from `api/`.
- Environment config is loaded once in `core/config.py` via `pydantic-settings`; never read `os.environ` directly elsewhere.
- Prefer explicit imports over wildcard imports.
- Format with `black`, lint with `ruff`.

### TypeScript / React (frontend)
- All new files use `.tsx` for components, `.ts` for pure logic.
- Props interfaces are defined inline above the component they belong to.
- API calls live in `src/services/`; components never call `fetch`/`axios` directly.
- Tailwind utility classes only — no custom CSS files unless absolutely necessary.
- Recharts components are wrapped in a local component in `src/components/charts/` to keep page files clean.

### Git
- Branch naming: `feat/`, `fix/`, `chore/`, `docs/` prefixes.
- Commit messages: imperative mood, ≤ 72 chars subject line.
- All PRs require passing CI (pytest + ruff + TypeScript type-check) before merge.

### AI (Claude integration)
- All prompts live in `backend/app/ai/prompts.py` as named constants — never inline strings in service code.
- Use prompt caching (`cache_control`) for long system prompts.
- Return structured data from Claude via tool use / structured output where possible.
- Model selection: default to `claude-sonnet-4-6`; escalate to Opus only for complex multi-step reasoning tasks.

---

## Security and Auth Rules

### Authentication
- Auth is JWT-based. Access tokens expire in **15 minutes**; refresh tokens expire in **7 days**.
- Access tokens are returned in the response body. Refresh tokens are set as `HttpOnly`, `Secure`, `SameSite=Strict` cookies — never in the response body or localStorage.
- Token refresh happens in `core/security.py` via a dedicated `/auth/refresh` endpoint. Route handlers never manually verify or refresh tokens; they depend on the `get_current_user` FastAPI dependency.
- On logout, the refresh token is added to a short-lived deny-list in Redis (or Postgres if Redis is unavailable) and the cookie is cleared.

### Password Storage
- Passwords are hashed with `bcrypt` via `passlib`. Work factor: 12 in production, 4 in tests (speed).
- Plain-text passwords never appear in logs, error messages, or response bodies — not even partially.

### Secret Handling
- All secrets (`ANTHROPIC_API_KEY`, `SECRET_KEY`, `DATABASE_URL`) come from environment variables loaded in `core/config.py`.
- Secrets are never committed, logged, or included in error responses.
- In logs, mask any field whose name contains `password`, `token`, `secret`, or `key` — replace value with `[REDACTED]`.
- In development, secrets live in `.env` (gitignored). In production, they are injected by Railway as environment variables.

### Rate Limiting
- Apply `slowapi` rate limiting at the FastAPI middleware level.
- Default limits: **60 requests/minute** per IP on public endpoints, **600 requests/minute** per authenticated user on API endpoints.
- AI summary endpoints: **10 requests/minute** per user (Claude calls are expensive).
- Rate limit headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`) are included in all responses.

### Input Validation
- All request bodies are validated by Pydantic schemas before reaching service code. Route handlers receive typed, validated objects — never raw dicts.
- String fields that feed into database queries must use parameterised SQLAlchemy expressions — never string interpolation.
- File uploads (if any) must be validated for MIME type, size limit (10 MB), and must be stored outside the web root.
- User-supplied experiment names and descriptions are sanitised (strip HTML) before storage to prevent stored XSS if values are later rendered.

---

## API Contract Standards

### Versioning
- All routes are prefixed `/api/v1/`. When a breaking change is required, introduce `/api/v2/` — do not modify v1 in place.
- A breaking change is: removing a field, changing a field's type, changing a status code on a success path, or removing an endpoint.
- Adding optional fields to a response is non-breaking and does not require a new version.

### Response Envelope
All API responses use a consistent envelope:

```json
// Success (single resource)
{ "data": { ... }, "meta": {} }

// Success (list)
{ "data": [ ... ], "meta": { "total": 120, "page": 2, "page_size": 20 } }

// Error
{ "error": { "code": "EXPERIMENT_NOT_FOUND", "message": "...", "details": {} } }
```

- `data` is never `null` on a 200; use 404 instead.
- `meta` is always present, even if empty `{}`.
- HTTP status codes are the primary signal; `code` in the error body is a machine-readable string for client logic.

### Pagination
- List endpoints accept `?page=1&page_size=20`. Default page size: 20. Maximum: 100.
- Response `meta` always includes `total`, `page`, and `page_size`.
- Cursor-based pagination may be added later for high-volume event endpoints; do not add it prematurely.

### Idempotency
- `POST /experiments` accepts an optional `Idempotency-Key` header (UUID). If a request with the same key was processed in the last 24 hours, return the original response without re-executing.
- Store idempotency keys in Postgres with a TTL. Implement in `services/idempotency_service.py`.
- `PUT` and `DELETE` are naturally idempotent by definition.

### Error Schema
- `400 Bad Request` — validation failure; `details` contains Pydantic field errors.
- `401 Unauthorized` — missing or invalid token.
- `403 Forbidden` — authenticated but not authorised for this resource.
- `404 Not Found` — resource does not exist or is not visible to this user.
- `409 Conflict` — state conflict (e.g. starting an already-running experiment).
- `422 Unprocessable Entity` — reserved for Pydantic validation errors (FastAPI default).
- `429 Too Many Requests` — rate limit hit; include `Retry-After` header.
- `500 Internal Server Error` — unexpected; log full traceback internally, return only `{ "error": { "code": "INTERNAL_ERROR", "message": "An unexpected error occurred." } }` to the client.

---

## Error Handling Conventions

### Backend — Services
- Services raise typed exceptions defined in `core/exceptions.py` (e.g. `ExperimentNotFoundError`, `AssignmentConflictError`).
- Services never raise `HTTPException` — that is the API layer's job.
- Exceptions carry a human-readable `message` and an optional `details` dict.

### Backend — API layer
- A global exception handler in `main.py` catches typed service exceptions and maps them to the correct HTTP status + error envelope.
- Unhandled exceptions are caught by a fallback handler that logs the traceback at `ERROR` level and returns a 500 with no internal details.
- Never let SQLAlchemy exceptions, Pydantic `ValidationError`, or raw `Exception` propagate to the client unhandled.

### Frontend
- Every data-fetching hook returns `{ data, isLoading, error }`. The `error` field is a typed `ApiError` object with `code` and `message`.
- Page components render an `<ErrorBanner>` component when `error` is set — they do not implement their own error UI.
- Network errors (timeout, offline) are distinguished from API errors in `src/services/apiClient.ts` and surfaced differently in the UI (toast vs. inline error).
- Never swallow errors silently. If a catch block can't recover, it must re-throw or set the error state.

---

## Experiment Integrity Rules

These rules are non-negotiable. Violating them invalidates statistical results.

### Assignment Stickiness
- Once a user (or device) is assigned to a variant, that assignment is permanent for the life of the experiment. Assignment is stored in the `assignments` table keyed on `(experiment_id, subject_id)`.
- `assignment_service.get_or_create_assignment()` is the only entry point for assignment. It uses `INSERT ... ON CONFLICT DO NOTHING` to make assignment atomic and idempotent under concurrent requests.
- Never re-assign a subject to a different variant mid-experiment, even if traffic weights change.

### Bucketing
- Variant assignment uses deterministic hashing: `hash(experiment_id + subject_id) % 10000` mapped to variant traffic buckets. This guarantees the same subject always lands in the same bucket.
- The hashing function is in `stats/bucketing.py`. Do not inline bucketing logic elsewhere.
- Salt each experiment with its own `randomisation_salt` (UUID generated at experiment creation) to prevent cross-experiment correlation.

### Re-randomization Prevention
- Experiments can never be paused and restarted with different traffic weights after assignment has begun. Changing traffic weights post-start is a configuration error and must be rejected with `409 Conflict`.
- If an experiment needs redesigning, it must be archived and a new experiment created.

### Delayed and Corrected Metrics
- Metrics may arrive late (e.g. conversion events with a 48-hour attribution window). The stats engine must support recomputing results against a specified `analysis_timestamp`, not just "now".
- Corrected events (e.g. refunded purchases) are handled by posting a negative-value event; the aggregation layer sums them. Services must never delete raw events.
- Sample ratio mismatch (SRM) is checked on every stats recomputation. If the observed assignment ratio deviates from the target by more than 1% (chi-squared p < 0.01), an `SRM_DETECTED` warning is attached to the result and surfaced in the UI.

---

## Performance Assumptions

| Concern | Assumption |
|---|---|
| Concurrent experiments | Up to 50 running simultaneously |
| Subjects per experiment | Up to 500,000 subjects |
| Event ingestion rate | Up to 500 events/second per experiment (burst) |
| Stats recomputation | Must complete in < 5 seconds for up to 1M events; use pre-aggregated daily rollups |
| AI summary generation | Target < 10 seconds end-to-end; stream the response if > 3 seconds |
| API p95 latency | < 200 ms for read endpoints, < 500 ms for write endpoints |
| Background jobs | Scheduled stats recomputation runs every 10 minutes via APScheduler |

Stats functions in `stats/` must be benchmarked in their unit tests using `pytest-benchmark` if they operate on arrays > 10,000 elements.

---

## Observability and Ops

### Logging
- Use Python's `structlog` for structured JSON logging in production, human-readable in development (controlled by `ENVIRONMENT`).
- Every log entry includes: `timestamp`, `level`, `service`, `request_id`, `user_id` (if authenticated), `experiment_id` (if relevant).
- Log levels: `DEBUG` (dev only), `INFO` (normal operations), `WARNING` (recoverable anomalies like SRM), `ERROR` (exceptions that need attention), `CRITICAL` (data integrity issues).
- Never log PII (email, name, IP address) except under a separate, explicitly opt-in audit log.
- Never log secrets. See Security section.

### Request Tracing
- Assign a `X-Request-ID` UUID to every incoming request (generate if not provided by caller). Propagate it in all log entries and downstream service calls for that request.
- The request ID is returned in the response header `X-Request-ID`.

### Metrics
- Expose a `/metrics` endpoint in Prometheus format via `prometheus-fastapi-instrumentator`.
- Track: request count by route/status, request duration (p50/p95/p99), DB query duration, Claude API call count and latency, SRM detection count.

### Alerting
- Alert on: error rate > 1% over 5 minutes, p95 latency > 1 second, any `CRITICAL` log entry, failed background job.
- Alert configuration lives in `infrastructure/` — not hardcoded in application code.

### Background Jobs
- Scheduled jobs (stats recomputation, SRM checks, report generation) run via APScheduler embedded in the FastAPI process.
- Each job logs its start, completion, and any errors with the job name and duration.
- Jobs are idempotent — re-running a job must not corrupt data.
- Long-running jobs (> 30 seconds) must update a `last_run_at` timestamp in Postgres so monitoring can detect stalled jobs.

### Migration Policy
- Migrations are run with `alembic upgrade head` as part of the deployment process, before new application code starts.
- Migrations must be backward-compatible with the previous application version (additive only: new tables, new nullable columns, new indexes). Never drop a column or rename a column in the same migration that adds business logic depending on it.
- Every migration file includes a `down_revision` and a working `downgrade()` function.
- Test migrations against a copy of production schema in the staging environment before deploying to production.

---

## AI Safety and Output Quality

### Prompt Versioning
- Every prompt constant in `prompts.py` has a version suffix: `EXPERIMENT_SUMMARY_PROMPT_V1`. When a prompt changes meaningfully, create a new constant (`_V2`) and update the caller — do not overwrite `_V1` in place until the old version is retired.
- The prompt version used for each AI call is stored alongside the result in the database for reproducibility.

### Fallback Behavior
- All Claude calls are wrapped in a try/except. If the API call fails (timeout, rate limit, API error), the service returns a structured fallback: `{ "summary": null, "recommendation": null, "error": "AI_UNAVAILABLE" }`.
- The frontend renders a "AI summary unavailable — view raw stats" state rather than an error page.
- Never block experiment creation, assignment, or stats computation on an AI call.

### Evaluation
- AI-generated summaries and recommendations are evaluated periodically against a held-out set of human-written summaries.
- New prompt versions must pass an offline evaluation (BLEU / human rating) before being promoted to production.
- Evaluation scripts live in `scripts/eval_ai.py`.

### Human Review Requirements
- AI-generated "stop experiment" or "declare winner" recommendations must be explicitly confirmed by a human in the UI before any state change occurs. The UI must display the AI's reasoning and the underlying stats side-by-side.
- AI-generated text that will be sent externally (e.g. in a report email) requires a review step in the UI before sending.
- Never treat Claude output as ground truth for statistical decisions — it is advisory only.

### Claude Code Review
- When Claude generates backend code, verify: type hints present, docstrings present, no `os.environ` calls, no inline SQL strings, no secrets in code.
- When Claude generates stats or ML code, always run the corresponding tests before trusting the output. Statistical code is subtly wrong more often than it looks.
- When Claude generates a migration, review it manually before running — auto-generated migrations frequently miss indexes or use unsafe column types.

---

## Frontend Architecture Details

### State Ownership
- **Server state** (experiments, metrics, results): managed by data-fetching hooks in `src/hooks/`. Do not copy server state into Zustand.
- **Global UI state** (auth session, sidebar open, toast notifications): managed by Zustand stores in `src/store/`.
- **Local component state** (form fields, modal open/closed, hover): managed by `useState` inside the component that owns it.
- When in doubt, keep state as local as possible and lift only when two sibling components genuinely need it.

### Loading and Error Patterns
- Every data-fetching hook must return `{ data: T | null, isLoading: boolean, error: ApiError | null }`.
- Pages use a `<PageShell>` component that accepts `isLoading` and `error` props and renders the appropriate skeleton or `<ErrorBanner>` — page components do not implement their own loading spinners.
- Skeleton loaders are used for initial page load. Inline spinners are used for subsequent mutations (button submits, etc.).
- Empty states (no experiments yet, no results yet) are distinct from loading and error states — render a dedicated `<EmptyState>` component, not a blank screen.

### Query Caching
- Use SWR or React Query (TBD — pick one and document here when decided) for data-fetching hooks. Do not hand-roll caching logic.
- Cache keys must include all parameters that affect the result: `['experiments', filters, page]`.
- Optimistic updates are allowed for low-stakes mutations (e.g. renaming an experiment). For high-stakes mutations (starting/stopping an experiment), wait for server confirmation before updating the UI.
- Stale-while-revalidate is the default strategy. Experiment detail pages poll every 30 seconds while an experiment is `RUNNING`.

### Chart Wrapper Conventions
- All Recharts usage is encapsulated in `src/components/charts/`. Pages import named chart components, not Recharts primitives directly.
- Chart components accept typed `data` props and handle their own responsive container and tooltip formatting.
- Charts must render a `<ChartEmptyState>` when `data` is empty, not a broken/empty Recharts canvas.
- Confidence interval bands are rendered as `<Area>` with 20% opacity over the primary `<Line>`.

### Design Tokens

All colours and fonts are CSS custom properties in `frontend/src/index.css`.

| Variable | Value | Purpose |
|---|---|---|
| `--color-bg-deep` | `#0A0E1A` | Page background |
| `--color-bg-card` | `#111827` | Card / panel surface |
| `--color-bg-elevated` | `#1A2234` | Table headers, dropdowns |
| `--color-bg-hover` | `#1E2D3D` | Hover state |
| `--color-border-subtle` | `#1E2D40` | Default border |
| `--color-border-active` | `#2A4A6B` | Focused border |
| `--color-accent-blue` | `#3B82F6` | Primary action, data |
| `--color-accent-green` | `#10B981` | Significant / positive |
| `--color-accent-amber` | `#F59E0B` | Warning / not-yet-significant |
| `--color-accent-red` | `#EF4444` | Danger / negative |
| `--color-text-primary` | `#F1F5F9` | Body text |
| `--color-text-secondary` | `#94A3B8` | Secondary labels |
| `--color-text-muted` | `#475569` | Placeholder, empty states |
| `--color-text-data` | `#60A5FA` | Inline metric values |

Fonts: `Syne` for headings, `DM Mono` for numeric data / code, `DM Sans` for body.

---

## Testing Matrix

### Coverage Expectations by Layer

| Layer | Minimum coverage | Test location |
|---|---|---|
| `stats/` | 100% line coverage | `tests/unit/test_stats_*.py` |
| `ml/` public functions | 100% line coverage | `tests/unit/test_ml_*.py` |
| `services/` | 80% line coverage | `tests/unit/test_*_service.py` |
| `api/v1/endpoints/` | Every route has at least one happy-path and one error-path test | `tests/integration/test_*_api.py` |
| `schemas/` | Validated implicitly by integration tests; no separate schema tests needed | — |
| Frontend hooks | Key hooks tested with `vitest` + `msw` for API mocking | `frontend/src/hooks/__tests__/` |
| Frontend utils | 100% for pure functions in `src/utils/` | `frontend/src/utils/__tests__/` |

### What Each Test Type Must Cover

**Unit tests (`tests/unit/`)**
- Stats functions: correct output for known inputs, edge cases (zero variance, all-control, n=1), and expected exceptions for invalid inputs.
- ML functions: correct output shape, no NaN in output, behaviour with missing features.
- Services: correct DB interactions (using mocked `AsyncSession`), correct exception types raised for error conditions.

**Integration tests (`tests/integration/`)**
- Every API endpoint: correct status code on success, correct error envelope on failure, authentication required where expected, pagination works.
- Assignment endpoint: concurrent assignment requests for the same subject produce the same variant (concurrency test with `asyncio.gather`).
- Database constraints: foreign key violations, unique constraints, and null constraints are enforced.

**Frontend tests**
- Data-fetching hooks: loading state transitions, error state on API failure, correct data shape returned.
- Pure utils: every exported function in `src/utils/` has a `vitest` test.
- Component smoke tests (optional): verify key components render without crashing given valid props.

### Running Tests

```bash
# All backend tests
cd backend && pytest

# Stats/ML unit tests only
pytest tests/unit/

# With coverage report
pytest --cov=app --cov-report=term-missing tests/

# Frontend
cd frontend && npm run test
```

---

## Data Retention and Privacy

- Raw assignment events are retained for **2 years** then purged.
- Aggregated metric rollups (daily sums) are retained indefinitely.
- Subject IDs stored in Axiom must be pseudonymous (hashed or opaque identifiers) — Axiom must never store raw emails, names, or device IDs in the `assignments` or `events` tables.
- Experiment results and AI-generated reports are retained for **5 years**.
- Data deletion requests (GDPR/CCPA) must be fulfillable by deleting all rows in `assignments` and `events` for a given `subject_id`. The `report` and `experiment` tables are not subject to per-user deletion.
- No analytics data is sent to third-party services. Prometheus metrics contain only aggregates — never per-user data.

---

## Deployment and Release Flow

### Environments

| Environment | Trigger | Database |
|---|---|---|
| `development` | Local `docker-compose up` | Local Postgres container |
| `staging` | Merge to `main` branch | Railway Postgres (staging) |
| `production` | Git tag `v*` (e.g. `v1.2.0`) | Railway Postgres (production) |

### Deployment Sequence
1. CI passes (pytest + ruff + TypeScript type-check).
2. Docker images are built and pushed to the container registry.
3. Database migrations run (`alembic upgrade head`) against the target environment's Postgres.
4. New application containers start.
5. Health check (`GET /health`) must return 200 within 60 seconds; otherwise the deployment is rolled back automatically.
6. Smoke tests (a small integration test suite) run against the live environment post-deploy.

### Migration Sequencing
- Migrations always run **before** new code. New code must be compatible with both the old and new schema during the deployment window.
- Multi-step migrations that require a data backfill must be split: (1) add column nullable, (2) deploy code that writes to it, (3) backfill existing rows, (4) add NOT NULL constraint in a later release.

### Rollback Policy
- Application rollback: re-deploy the previous Docker image tag. This takes < 2 minutes.
- Database rollback: run `alembic downgrade -1`. Only possible if the migration has a working `downgrade()` and the rollback is executed before the next migration runs.
- If a migration cannot be rolled back safely, it must be fixed forward with a new migration.
- The last three production image tags are always retained in the registry.

### Release Gates
- No deploy to production unless staging has been running the same image for at least **30 minutes** with no error-rate alerts.
- No deploy to production during weekends or public holidays unless it is a critical hotfix.
- Any change to `stats/` or `ml/` requires a sign-off in the PR from a reviewer who understands the statistical implications.
- Any change to `ai/prompts.py` requires an offline evaluation run (see AI Safety section) before merging.

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `ANTHROPIC_API_KEY` | Claude API key |
| `SECRET_KEY` | JWT signing key |
| `ENVIRONMENT` | `development` / `staging` / `production` |

---

## Running Locally

```bash
# Backend
cd backend
python -m uvicorn app.main:app --reload

# Frontend (Node 18+ required — system default may be older)
cd frontend
PATH="/usr/local/opt/node/bin:$PATH" npm run dev

# Full stack
docker-compose up
```

## Testing

```bash
# All backend tests
cd backend && pytest

# Stats/ML unit tests only
pytest tests/unit/

# With coverage
pytest --cov=app tests/
```
