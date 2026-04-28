# Axiom — AI-Powered A/B Testing Platform

## What Axiom Does

Axiom is an intelligent experimentation platform that lets teams design, run, and analyze A/B tests with statistical rigor and ML-assisted insights. It handles experiment lifecycle management (creation, audience assignment, traffic splitting), computes frequentist and Bayesian statistics on results, and uses Claude to generate plain-language summaries and recommendations. A React dashboard surfaces live experiment status, metric charts, and AI-generated reports.

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

# Frontend
cd frontend
npm run dev

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
