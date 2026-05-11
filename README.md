![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-894%20passing-22c55e)
![Coverage](https://img.shields.io/badge/Coverage-%E2%89%A585%25-22c55e)
![License](https://img.shields.io/badge/License-MIT-6366f1)

# Axiom — AI-Powered A/B Testing Platform

Most A/B tests are wrong before the data even comes in. Teams peek at results early and stop when they see significance. They track five metrics but only report the one that moved. They ignore the fact that a 12% average lift hides a 40% lift for mobile users and a –8% lift for everyone else. Axiom is built specifically to fix that.

## What It Does

Axiom is a self-hosted experimentation platform that enforces statistical correctness at every step — from experiment design through analysis. It uses sequential testing to eliminate peeking bias, Benjamini-Hochberg correction to control false discovery rate across multiple metrics, and CUPED variance reduction to get to significance faster with the same sample size. On top of the stats engine, a Claude-powered AI layer generates plain-English interpretations streamed live to the dashboard, so analysts spend time deciding rather than writing.

## Live Demo

**[GitHub](https://github.com/anika0273/axiom)** — Railway deployment link available after setup

The frontend includes a zero-API-call **Demo Mode** with three pre-computed datasets (e-commerce checkout, SaaS onboarding, marketplace listings). Click **Try Demo** on the home page — no account required, no backend needed.

---

## The 5 Problems It Solves

| Problem | What goes wrong | Axiom's solution |
|---|---|---|
| **Peeking** | Stopping a test when p < 0.05 inflates false-positive rate to ~30% | Sequential testing (SPRT) with always-valid p-values — safe to check any time |
| **Multiple metrics** | 10 metrics × 0.05 ≈ 40% chance of at least one false positive | Benjamini-Hochberg FDR correction applied automatically across all metrics |
| **High variance** | Noisy metrics need 2× the sample size | CUPED pre-experiment covariate adjustment; typically 20–40% variance reduction |
| **Average hides segments** | A flat average lift conceals opposite effects in subgroups | ML heterogeneous treatment effect (HTE) analysis surfaces segments automatically |
| **Manual reporting** | Writing stakeholder reports takes hours | Claude generates an 8-section structured report, streamed live via SSE |

---

## Architecture

```
                          ┌─────────────┐
  Browser ──── HTTPS ───▶ │    nginx     │  reverse proxy (port 80)
                          │  (alpine)   │  /api/* → backend
                          └──────┬──────┘  /*    → frontend
                                 │
               ┌─────────────────┴──────────────────┐
               ▼                                    ▼
      ┌──────────────────┐               ┌──────────────────┐
      │  FastAPI backend │               │  React + Vite    │
      │  (Python 3.12)   │               │  (nginx static)  │
      │                  │               │                  │
      │  stats/          │               │  pages/          │
      │  ml/             │               │  hooks/          │
      │  intelligence/   │               │  components/     │
      └────────┬─────────┘               └──────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
 ┌──────────┐   ┌──────────────┐
 │ Postgres │   │  Claude API  │
 │    15    │   │ (Anthropic)  │
 └──────────┘   └──────────────┘

All services run on an internal Docker bridge network.
Only nginx binds a host port.
```

---

## Tech Stack

| Technology | Role | Why this choice |
|---|---|---|
| **FastAPI** (Python 3.12) | REST API + SSE streaming | Async-native, automatic OpenAPI docs, type-safe request/response via Pydantic |
| **PostgreSQL 15** | Persistence | JSONB for flexible metric schemas; window functions for rollup queries |
| **SQLAlchemy 2 (async)** | ORM | `AsyncSession` + connection pooling; Alembic for versioned migrations |
| **React 18 + Vite** | Frontend | `React.lazy` route splitting; concurrent rendering for smooth streaming UI |
| **Recharts** | Charts | Composable primitives; `<Area>` confidence interval bands without a charting DSL |
| **Anthropic SDK** | AI layer | Streaming tool_use responses; prompt caching on long system prompts |
| **Docker + nginx** | Deployment | Internal network isolation; only nginx faces the public internet |
| **Railway** | Hosting | Zero-config Postgres provisioning; env var injection; `v*` tag deploys to production |
| **GitHub Actions** | CI | Integration tests against live Claude API run on a weekly schedule with secrets injection |

---

## Statistical Methods

| Method | Problem it solves | Where implemented |
|---|---|---|
| Two-proportion z-test | Binary conversion metrics | `backend/app/stats/testing.py` |
| Welch's t-test | Continuous metrics (revenue, time) | `backend/app/stats/testing.py` |
| CUPED variance reduction | Cuts required sample size by 20–40% | `backend/app/stats/cuped.py` |
| Sequential testing (SPRT) | Makes peeking statistically valid | `backend/app/stats/sequential.py` |
| Bonferroni correction | Conservative multi-metric control | `backend/app/stats/corrections.py` |
| Benjamini-Hochberg FDR | Balanced multi-metric control | `backend/app/stats/corrections.py` |
| Power analysis | Required sample size calculation | `backend/app/stats/power.py` |
| Sample ratio mismatch (SRM) | Detects broken randomization | `backend/app/stats/engine.py` |

430 unit tests cover every method, including edge cases (zero variance, n=1, all-control groups). Line coverage: 96%.

---

## ML Methods

| Method | What it finds | Where implemented |
|---|---|---|
| Causal forest (HTE) | Subgroups with above/below-average treatment effect | `backend/app/ml/hte.py` |
| K-means + SHAP | Segments defined by feature importance, not just averages | `backend/app/ml/segments.py` |
| Isolation forest | Anomalous metric spikes that may indicate instrumentation bugs | `backend/app/ml/anomaly.py` |
| Novelty scoring | Flags users whose behaviour is outside training distribution | `backend/app/ml/novelty.py` |
| ML orchestration | Validates inputs; routes to correct model; returns unified result | `backend/app/ml/engine.py` |

751 unit tests. All modules ≥ 93% coverage.

---

## AI Integration

Claude (`claude-sonnet-4-6`) is used in three distinct ways, each with separate guardrails:

**1. Experiment Planner** (`intelligence/planner.py`)
Takes a natural-language experiment description and uses Claude's `tool_use` to return a structured `ExperimentPlan` — hypothesis, primary/secondary metrics, required sample size (verified against the stats engine), and recommended test duration. The planner is the backend for the wizard UI.

**2. Result Interpreter** (`intelligence/interpreter.py`)
Streams a plain-English explanation of experiment results via Server-Sent Events. A grounding validator runs post-stream to catch hallucinated lift numbers — if Claude says "23% lift" but the data shows 8%, it's corrected before the UI renders it.

**3. Stakeholder Reporter** (`intelligence/reporter.py`)
Generates an 8-section report (executive summary, methodology, results, risks, recommendation, and more) via `tool_use`. Section 8 — the final recommendation — is always assembled programmatically from raw stats, never from Claude's free text, to prevent AI-generated "declare winner" decisions from bypassing human review.

**Prompt engineering details:**
- All prompt templates are versioned (`_V1` suffix); old versions are never overwritten in place
- `cache_control` is applied to long system prompts — repeat calls within a session hit the cache
- All Claude calls wrapped in a fallback layer: if the API is unavailable, template-based responses keep the rest of the platform working
- AI-generated "stop experiment" recommendations require explicit human confirmation in the UI before any state change

---

## What I Learned

**Hard parts:**

- **Statistical correctness under load.** The SRM check, CUPED computation, and sequential boundary all need to be correct simultaneously on the same result object. Getting 430 tests green required thinking carefully about which parts of the computation are statistically independent and which aren't.

- **CUPED implementation.** The textbook description is clean; the production version is not. Handling missing pre-experiment covariates, deciding what to do when variance is near-zero, and making the adjustment numerically stable across different metric scales took several iterations.

- **SSE streaming in FastAPI.** FastAPI's `StreamingResponse` with `text/event-stream` works, but backpressure handling, client disconnect detection, and reconnect behavior in the React `EventSource` hook all need explicit attention. The grounding validator that runs post-stream to catch hallucinated numbers was a late addition that required restructuring how the stream buffer works.

- **Keeping 894 tests green across 5 phases.** Stats tests break when ML code changes shared utilities. Intelligence tests break when schema changes alter the Pydantic models that Claude's tool_use output is validated against. The discipline of running the full suite before every commit was the only thing that kept this manageable.

- **Production network isolation.** Getting the Docker network right so only nginx faces the public internet, backend and frontend are invisible to the host, and health checks work correctly across the internal bridge — all while keeping the dev `docker-compose.yml` simple enough to use daily — required three iterations.

---

## Quick Start

```bash
git clone https://github.com/anika0273/axiom.git && cd axiom

cp .env.example .env  # add ANTHROPIC_API_KEY and a random SECRET_KEY

docker compose up -d

docker compose exec backend alembic upgrade head && \
  docker compose exec backend python backend/migrations/seeds.py

open http://localhost
```

No account needed. The seeded database includes a complete experiment with results and a pre-generated AI report. Hit **Try Demo** on the home page for a fully offline walkthrough.

---

## Test Suite

| Phase | Tests | What's covered |
|---|---|---|
| **Stats engine** | 430 | z-test, t-test, CUPED, sequential, corrections, power, SRM — edge cases and expected exceptions |
| **ML engine** | 321 | HTE, segment discovery, anomaly detection, novelty scoring, ML orchestration |
| **AI intelligence** | 107 | Planner, interpreter, reporter, guardrails, fallbacks, cost estimation |
| **API integration** | 36+ | Every endpoint: happy path + error path + auth + pagination |
| **Total** | **894** | |

```bash
# Run everything
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/ --cov=backend/app -q

# Stats only
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/stats/ backend/tests/unit/ -q

# AI intelligence only
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/intelligence/ -q

# Frontend
cd frontend && npm run test
```

Weekly CI runs the full integration test suite against the live Claude API using GitHub Actions (`.github/workflows/integration-tests.yml`).

---

## License

MIT
