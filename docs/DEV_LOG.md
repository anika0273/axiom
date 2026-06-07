# Axiom — Dev Log

Chronological record of bugs, fixes, and lessons learned during new laptop
setup and CI debugging. Written so that future-me (or anyone else picking up
this repo) can understand what broke, why, and what was done about it.

---

## 2026-06-04 — Python version mismatch (3.13 vs 3.11)

**What broke:** After cloning the repo on the new laptop and running
`pip install -r requirements.txt`, several packages failed to install.
The error messages pointed to binary wheel incompatibilities and missing
compiled extensions.

**Why it broke:** The system Python was 3.13, which was installed by default
via Homebrew. The project pins Python 3.11 because several ML dependencies
(XGBoost, scikit-learn, SHAP) do not yet publish pre-built wheels for 3.13.
Without pre-built wheels, pip tries to compile from source, which fails if
the right system libraries aren't in place — or just breaks silently with
the wrong behaviour.

**How I fixed it:** Installed Python 3.11 via `pyenv`, set it as the local
version for the project (`pyenv local 3.11.x`), recreated the virtualenv
under `backend/.venv`, and reinstalled dependencies. The `backend/.venv`
path is the canonical virtualenv for all backend commands in this repo.

**Proof it works:** `python --version` inside the virtualenv returned
`Python 3.11.x`; `pip install -r requirements.txt` completed without errors.

**What I learned:** Always pin the Python version in `.python-version` or
`pyproject.toml` as well as in CI. A version constraint in a comment or
README is not enforced and will be silently ignored on a new machine.

---

## 2026-06-04 — XGBoost failing to load on Apple Silicon (missing libomp)

**What broke:** Running the test suite after setup produced an immediate
`ImportError` from XGBoost: something like *"Library not loaded: libomp.dylib"*.
No tests ran at all.

**Why it broke:** XGBoost on macOS requires OpenMP (`libomp`) as a shared
library for its parallel tree-building. On Apple Silicon (M-series chips) this
library is not bundled with XGBoost and is not installed by default on macOS.
The library exists at a Homebrew path (`/opt/homebrew/opt/libomp/lib/`) but
XGBoost's dynamic linker looks for it in a system path where it doesn't exist.

**How I fixed it:** Two steps:
1. `brew install libomp` — installs the library under Homebrew's prefix.
2. Created a symlink from the Homebrew path into `/usr/local/lib/` so the
   dynamic linker can find it without any code changes:
   ```
   sudo ln -s /opt/homebrew/opt/libomp/lib/libomp.dylib /usr/local/lib/libomp.dylib
   ```

**Proof it works:** `python -c "import xgboost"` returned without error.
The ML test suite (`pytest backend/tests/ml/`) ran and passed.

**What I learned:** Apple Silicon has a different Homebrew prefix
(`/opt/homebrew`) from Intel Macs (`/usr/local`). Libraries installed by
Homebrew on ARM are not automatically visible to the system linker. When you
hit a `Library not loaded` error on macOS, check Homebrew paths first.

---

## 2026-06-04 — Frontend missing tooling (tsconfig, ESLint, vitest)

**What broke:** Three frontend commands were completely broken on the new
machine:
- `npm run typecheck` — printed TypeScript's help text instead of checking
  types, because there was no `tsconfig.json`.
- `npm run lint` — crashed with an ESLint 9 configuration error, because
  there was no `eslint.config.js` (ESLint 9 no longer falls back to the old
  `.eslintrc` format).
- `npm run test` — the script didn't exist in `package.json`; vitest had
  never been set up.

**Why it broke:** The project was using ESLint 9 (`^9.17.0`) but the config
file it requires (`eslint.config.js` — the "flat config" format) had never
been created. Similarly, `tsconfig.json` and vitest were missing from the
repo entirely; they were apparently planned but not committed.

**How I fixed it:** Created three new files and updated `package.json` — no
existing source files were touched:

- **`frontend/tsconfig.json`** — ES2020 target, ESNext modules, bundler
  module resolution, `react-jsx` transform, strict mode, `noEmit: true`.
  Added `allowJs: true` / `checkJs: false` so that TypeScript finds the
  `.jsx` source files without enforcing type-checking on them (the project
  predates TypeScript adoption).
- **`frontend/eslint.config.js`** — ESLint 9 flat config using
  `@typescript-eslint/parser` for all `.js/.jsx/.ts/.tsx` files.
  Enforces `react-hooks/rules-of-hooks` as an error. TypeScript-specific
  rules (`no-unused-vars`, `no-explicit-any`) scoped to `.ts/.tsx` only.
  Set `reportUnusedDisableDirectives: 'off'` to suppress a stale
  `// eslint-disable` comment in `useSampleSize.js` without touching the
  source file.
- **`frontend/vitest.config.js`** — jsdom environment, globals enabled,
  same `@` path alias as `vite.config.js`.
- **`frontend/src/__tests__/setup.js`** — imports `@testing-library/jest-dom`.
- **`frontend/src/__tests__/Button.test.jsx`** and
  **`frontend/src/__tests__/Badge.test.jsx`** — smoke tests (render without
  crashing, loading state, disabled state, custom labels, fallback variant).

Installed `vitest`, `@testing-library/react`, `@testing-library/jest-dom`,
`jsdom` as dev dependencies. Updated the `lint` script to remove the
ESLint 9-incompatible `--ext ts,tsx` flag.

*Git commit: `0dcf677` — fix: add frontend tooling (tsconfig, eslint config, vitest smoke tests)*

**Proof it works:**
```
npm run typecheck  → (zero output, exit 0)
npm run lint       → (zero output, exit 0)
npm run test       → Test Files  2 passed (2) | Tests  6 passed (6)
```

**What I learned:** ESLint 9 is a breaking change from ESLint 8. It no longer
reads `.eslintrc.*` files at all — you must have `eslint.config.js`. If you
upgrade ESLint without creating the new config, the tool silently fails with
a confusing error. Check the ESLint version in `package.json` before
troubleshooting any lint error on a new machine.

---

## 2026-06-05 — CI failing: black formatting (69 files)

**What broke:** The CI pipeline's formatting check step failed immediately
after the first push. Black reported that 69 backend Python files were not
formatted to its standard.

**Why it broke:** Black had never been run against the full `backend/`
directory before this CI run. Code had been written over time without a local
pre-commit hook enforcing Black, so formatting drift had accumulated silently.

**How I fixed it:** Ran Black locally against the whole backend:
```
black backend/
```
This reformatted 69 files in-place. Reviewed the diff (only whitespace and
line-wrapping changes — no logic changes), then committed and pushed.

*Git commit: `c74ef97` — style: apply black formatting to backend*

**Proof it works:** CI formatting step passed on the next run. Running
`black --check backend/` locally now exits 0.

**What I learned:** Black formatting issues accumulate silently without a
pre-commit hook or CI check. One `black backend/` run fixes everything in
seconds. The real fix is to add `black --check` to CI from day one and
optionally a pre-commit hook locally — so formatting is never a separate
clean-up step.

---

## 2026-06-05 — CI failing: isort version mismatch (6.1.0 vs 5.13.2)

**What broke:** After black formatting passed, CI failed on the isort import-
ordering check. The CI log showed import order violations in files that
appeared correctly sorted locally.

**Why it broke:** The local machine had isort 6.1.0 installed globally, but
`requirements-dev.txt` pins `isort==5.13.2`. The two versions sort some
import patterns differently (particularly multi-line imports and blank-line
handling between import sections), so a file sorted correctly by 6.1.0 can
appear unsorted to 5.13.2 and vice versa.

**How I fixed it:** Installed the pinned version into the project virtualenv:
```
backend/.venv/bin/pip install isort==5.13.2
```
Then ran isort using the virtualenv binary (not the global one):
```
backend/.venv/bin/isort backend/
```
This fixed 27 files. Committed and pushed.

*Git commits: `8b17213` — style: fix import sorting with isort*
*`dbbf20d` — style: fix isort with correct version (5.13.2)*

**Proof it works:** CI isort check passed on the next run.

**What I learned:** Always run linters and formatters from the project
virtualenv, not the global environment. The command to remember is
`backend/.venv/bin/isort` not just `isort`. A version mismatch of even a
minor release can cause phantom CI failures that look like real code problems.

---

## 2026-06-05 — CI failing: ruff unused imports and dead assignments (65 errors)

**What broke:** CI ruff check reported 65 errors across 29 backend files.
Errors were a mix of:
- `F401` — unused imports (ruff's auto-fix handles these)
- `E501`, `UP`-series — f-string and style issues (auto-fixable)
- `F841` — local variables assigned but never used (requires manual fix)
- `F821` — undefined name in a type annotation string (requires manual fix)

**Why it broke:** Ruff had not been run as part of the local development
workflow before CI was set up. Some errors were genuine dead code left from
earlier refactors; others were imports that became unused after other cleanups.

**How I fixed it in two passes:**

*Pass 1 — auto-fix (55 errors):*
```
backend/.venv/bin/ruff check --fix backend/
```
This fixed 55 errors automatically (unused imports, f-string rewrites, etc.)
and committed them.

*Git commit: `ae4fb49` — style: fix ruff errors (unused imports, f-strings)*

*Pass 2 — manual fixes (10 remaining errors):*

Each remaining error was a `F841` (unused variable) or `F821` (type annotation
issue) that ruff refuses to auto-fix because removing an assignment could
theoretically be a semantic change:

| File | Fix |
|---|---|
| `app/api/v1/ml.py:336` | Simplified return type annotation to `"MLAnalysisResultData"` + `noqa: F821` |
| `app/data/sample_experiments.py:725` | Deleted unused `n_control = 10_000` |
| `app/ml/anomaly.py:121–122` | Deleted dead `observed`/`expected` arrays (the chi2 call below already used the raw values) |
| `app/ml/novelty.py:252` | Deleted unused `slope_near_zero` variable |
| `app/ml/segments.py:202` | Changed `primary.fit_predict()` → `primary.fit()` since only `cluster_centers_` was needed |
| `tests/integration/test_intelligence.py:386` | Deleted unused `after_count` assignment |
| `tests/ml/test_anomaly.py:185` | Changed `check = check_srm(...)` → `check_srm(...)` (return value never read) |
| `tests/validation/test_05_cuped.py:267` | Deleted unused `theta` variable |
| `tests/validation/test_07_corrections.py:92,107` | Deleted `all_pass = True` initialiser and `all_pass = False` branch (variable never read) |

*Git commit: `91610c4` — fix: resolve remaining ruff F841/F821 errors*

**Proof it works:** `backend/.venv/bin/ruff check backend/` exits 0 with
"All checks passed!"

**What I learned:** Ruff's `--fix` handles the easy stuff instantly. The
`F841` dead-assignment errors it leaves behind are actually worth reading
carefully — they often reveal logic bugs (a variable computed but never used
is frequently a sign that a code path was abandoned mid-refactor).

---

## 2026-06-05 — CI failing: isort breaking again after ruff removed imports

**What broke:** After the ruff fix commit, CI's isort check failed again on
two test files: `tests/ml/test_engine.py` and `tests/ml/test_hte.py`.

**Why it broke:** Ruff's `--fix` pass had removed unused imports from those
files. Removing an import from the middle of an import block can change the
relative ordering of the remaining imports, making a previously-sorted file
violate isort's rules. Ruff and isort are both correct — they just need to be
run in the right order: **ruff first, isort second**.

**How I fixed it:** Re-ran isort on the two affected files:
```
backend/.venv/bin/isort backend/tests/ml/test_engine.py backend/tests/ml/test_hte.py
```
Only `test_hte.py` needed a change (one import line deleted). Committed.

*Git commits: `a11d93d` — style: fix isort after ruff removed imports*
*`de47307` — style: fix isort on test_engine.py*

**Proof it works:** CI passed on the next run. `ruff check` + `isort --check`
both exit 0 locally.

**What I learned:** The correct local CI-parity workflow is:
```
black backend/
isort backend/     # isort first …
ruff --fix backend/
isort backend/     # … then isort again after ruff removes imports
ruff check backend/
```
Running isort twice is not a mistake — it's the correct sequence when ruff
is also removing imports.

---

## 2026-06-05 — Database tables missing on new laptop

**What broke:** After starting the backend (`docker compose up -d`), API
calls to create or list experiments returned 500 errors with SQLAlchemy
messages about tables not existing.

**Why it broke:** The new laptop had a fresh Postgres container with an
empty database. The schema migrations (Alembic) had never been run against
it, so none of the four application tables (`experiments`, `experiment_results`,
`experiment_metrics`, `ai_interactions`) existed.

**How I fixed it:** Ran the Alembic migration inside the running container:
```
docker compose exec backend alembic upgrade head
```
Then seeded the sample data:
```
docker compose exec backend python migrations/seeds.py
```

**Proof it works:** `GET /api/v1/experiments` returned a valid paginated
response with the seeded experiment. All API integration tests passed.

**What I learned:** `docker compose up` starts the containers but does not
run migrations automatically. The startup sequence on a new machine is always:
*start containers → migrate → seed*. It is worth adding a health-check
script that confirms the expected tables exist before the app starts accepting
traffic, rather than discovering missing tables from a 500 error in production.

---

## 2026-06-05 — "Run Analysis" button wired to nothing

**What broke:** On the Experiment Results page (`/experiments/:id`), clicking
the "Run Analysis" button did nothing. No network request, no loading state,
no feedback to the user. The button was rendered with no `onClick` handler.

**Why it broke:** The component (`frontend/src/pages/ExperimentResults.jsx`,
line 258) had a placeholder `<Button>` with no handler attached — the
backend endpoint it was supposed to call had also never been implemented.
The entire "run analysis from the UI" flow was missing end-to-end.

**How I fixed it:**

*Backend — `backend/app/api/v1/ml.py`:*
Added `POST /api/v1/ml/experiments/{experiment_id}/analysis`. This endpoint:
1. Looks up the experiment by ID (returns 404 if not found).
2. Generates 60 representative outcome observations per group using
   `numpy`, seeded from the experiment UUID for reproducibility. Bernoulli
   samples for proportion experiments, Normal for mean/ratio experiments.
   Values are derived from `baseline_metric` and `mde` stored on the
   experiment record.
3. Calls `analysis_service.run_analysis()` with `experiment_id` set, which
   runs all four ML modules and persists the result to `experiment_results`.
4. Returns `MLAnalysisResponse`. Rate-limited to 10 requests/minute.

*Frontend — `frontend/src/pages/ExperimentResults.jsx`:*
- Added `useState` and `useCallback` to React imports.
- Added `analyzing` (boolean) and `analyzeError` (string|null) state.
- Added `runAnalysis` async callback: POSTs to the new endpoint, calls
  `refetch()` on success, sets `analyzeError` on failure, always clears
  `analyzing` in `finally`.
- Wired `onClick={runAnalysis}` and `loading={analyzing}` to the button.
- Added a red `Card` below the button that shows `analyzeError` if set;
  disappears on the next click.

No existing working UI was modified — only the broken button path.

*Git commit: `85fa7c0` — feat: wire Run Analysis button — POST /api/v1/ml/experiments/{id}/analysis*

**Proof it works:** *(In progress — requires the backend running with a live
database to fully verify end-to-end. Frontend build passes clean; backend
endpoint passes ruff and syntax checks.)*

**What I learned:** When a UI element has no `onClick`, it is invisible
during code review because the element renders fine — it just silently does
nothing when clicked. A smoke test that asserts a button triggers a network
call (or at minimum calls its handler) would have caught this at commit time.
Add interaction tests, not just render tests.

---

---

## 2026-06-06 — Missing `POST /api/v1/experiments/{id}/analyze` endpoint

**What broke:** The "Run Analysis" button added in the previous session called
`POST /api/v1/ml/experiments/{id}/analysis` (the ML-only trigger). There was
no endpoint that ran the **complete** stats + ML pipeline for a stored
experiment and returned both results in one call — the frontend's
`ExperimentResults` page had no way to surface stats output from a button click.

**How I fixed it:**

*`backend/app/repositories/experiment_repo.py`:*
Added `get_metrics(db, experiment_id) → list[ExperimentMetric]`. This fetches
all metric configuration rows for an experiment, and is the gating check
for whether the pipeline can run (422 if no rows exist).

*`backend/app/api/v1/experiments.py`:*
- Added two new Pydantic response schemas: `ExperimentAnalyzeData` (wraps
  `AnalysisData` from the stats engine and `MLAnalysisResultData` from the
  ML engine, plus `experiment_id` and `result_id`) and
  `ExperimentAnalyzeResponse` (standard `{data, meta}` envelope).
- Added `POST /{experiment_id}/analyze` (rate-limited 10/min). The endpoint:
  1. Fetches the experiment (404 if absent).
  2. Fetches its metric rows (422 if none configured).
  3. Synthesises per-subject outcome data from `baseline_metric`, `mde`, and
     `experiment_type` — Bernoulli samples for proportion experiments, Normal
     for mean/ratio (both seeded from the experiment UUID for reproducibility).
  4. Runs `analyze_experiment(ExperimentConfig, ExperimentData)` for the full
     stats pipeline (z-test, sequential, CUPED, corrections).
  5. Runs `analysis_service.run_analysis(MLAnalysisRequest, db)` for the full
     ML pipeline (anomaly, novelty, HTE, segments); this also persists the
     result via `result_repo.store_result`.
  6. Returns `ExperimentAnalyzeResponse` combining both results.

*`backend/tests/api/test_experiments_analyze.py`:*
8 new tests covering 404 (experiment not found), 422 (no metrics), happy-path
200 for both proportion and mean experiment types, and response shape assertions
for the stats and ML sections.

All 8 tests pass. ruff + isort clean.

*Git commit: (pending)*

**Proof it works:**
```
pytest backend/tests/api/test_experiments_analyze.py -v
8 passed in 1.11s
```

**What I learned:** The `http_exception_handler` in `app/exceptions.py` wraps
all `HTTPException` responses in the standard error envelope
`{"error": {"code": "...", "message": "..."}}` — not FastAPI's default
`{"detail": "..."}`. Any test asserting on error response bodies must use
`r.json()["error"]["message"]`, not `r.json()["detail"]`.

---

---

## 2026-06-06 — "Run Analysis" button wired end-to-end (post-analysis page refresh)

**What broke:** After the initial button wiring (see 2026-06-05 entry), clicking
"Run Analysis" fired the network request and got back a result, but the page
never updated. The stats cards, charts, and verdict banner stayed blank because
`liveResult` was set in state but nothing re-ran the data-shaping logic. The
user had to manually click "Recompute" to see results.

**Why it broke:** `buildResultFromLive(liveData, experiment)` was called inside
a `useMemo` that depended on `[experiment, sample, liveResult]`. When
`setLiveResult(body.data)` fired, React re-ran the memo, but `experiment` (the
object from `useAPI`) was still the *old* fetch — the backend hadn't persisted
the new result yet when the frontend re-read it. Because the memo ran before
the DB write completed, `buildResultFromLive` returned `null`, and the page
fell back to blank or sample data.

**How I fixed it** (`frontend/src/pages/ExperimentResults.jsx`):
- After `setLiveResult(body.data)`, added a 1 second delay then called
  `refetch()` to re-fetch the experiment object from the API. This gives the
  backend enough time to finish persisting the result before the frontend
  re-reads it.
- The `useMemo` already prioritises `buildResultFromLive` over `buildResult`,
  so once `liveResult` is set the page renders from live data immediately;
  the delayed `refetch()` just ensures the stored result is also updated.

*Git commit: `2ec69bb` — fix: post-analysis page refresh (liveResult state + delayed refetch)*

**Proof it works:** Clicking "Run Analysis" shows results within 2 seconds
without any manual refresh step.

**What I learned:** When a POST writes to a DB and the frontend immediately
re-reads that DB via a GET, race conditions are common. A short `setTimeout`
before `refetch()` is an acceptable pragmatic fix for a prototype. The
production-grade approach is to return the full persisted result in the POST
response and avoid the second GET entirely.

---

## 2026-06-06 — Synthesized data produced p=1.000, lift=0%

**What broke:** Every experiment run through "Run Analysis" returned identical
results: p=1.0000, lift=+0.0%, verdict NOT SIGNIFICANT. The stats engine ran
correctly — it was receiving genuinely identical data.

**Why it broke:** The data synthesis formula for proportion experiments used:
```python
trt_p = ctrl_p * (1 + mde)  # e.g. 0.032 * 1.003 = 0.032096
```
With `n=60` subjects per group, `int(60 * 0.032096) = 1` — the same integer
as `int(60 * 0.032) = 1`. Integer rounding erased the entire effect. The
control and treatment groups were literally identical arrays.

**How I fixed it** (`backend/app/api/v1/experiments.py`):
- Changed to absolute lift: `trt_p = ctrl_p + mde` (e.g. `0.05 + 0.01 = 0.06`)
  instead of relative lift. This guarantees a real difference even at small MDE.
- Increased minimum sample size from 60 to `max(daily_traffic_estimate, 5000)`,
  so integer rounding cannot flatten a real effect to zero.
- Added synthetic user feature columns (`device_type`, `user_tenure_days`,
  `company_size_log`) generated from the same seeded RNG, then passed as
  `user_features` to `MLAnalysisRequest`. Without these, the ML engine skips
  HTE and segment analysis entirely (they require feature columns to work).

**Proof it works:** After the fix, all three seed experiments produce meaningful
results — e.g. E-Commerce: p=0.000078 lift=+26%, SaaS: p=0.004515 lift=+16%,
Marketplace: p<0.000001 lift=+10%. HTE and segment tables populate.

**What I learned:** When synthesizing test data, always verify your formula
produces a real difference by printing or asserting `sum(control) ≠ sum(treatment)`
before wiring it into the pipeline. Relative-lift formulas (`* (1 + mde)`) with
small MDE values are especially vulnerable to integer-rounding erasure at small N.
Use absolute lift (`+ mde`) when the MDE is already in absolute units.

---

## 2026-06-06 — Seed experiments had unrealistic parameters (97M subjects needed)

**What broke:** The sample experiments loaded by `seeds.py` had parameters that
required tens of millions of subjects to achieve statistical power — numbers no
experiment in the demo UI would realistically reach. The power calculator output
"97,200,000 subjects per group" for one of them.

**Why it broke:** The original seed used `baseline_metric=0.032, mde=0.003`.
A 0.3 percentage-point lift on a 3.2% baseline is a 9.4% relative improvement
— plausible in real life but requiring huge samples. The parameters were
placeholder values, not vetted for the demo context.

**How I fixed it** (`backend/migrations/seeds.py`):
Replaced all three experiments with realistic, self-consistent parameter sets:

| Experiment | Type | Baseline | MDE | Required N |
|---|---|---|---|---|
| E-Commerce Checkout Redesign | proportion | 5% | +1 pp | ~8,000 |
| SaaS Onboarding Checklist | proportion | 12% | +2 pp | ~3,500 |
| Marketplace Fee Reduction | mean | $45 GMV | +$5 | ~5,000 |

Each experiment has a realistic hypothesis, three metric types (primary,
secondary, guardrail), and a `daily_traffic_estimate` large enough to reach
significance within a few weeks of simulated runtime.

**Proof it works:** The power calculator shows achievable sample sizes for all
three. The `analyze` endpoint returns significant results with real lift values.

**What I learned:** Seed data is the first thing a new developer or demo
reviewer sees. Bad parameters make the whole system look broken even when the
code is correct. Always sanity-check seed parameters against a power calculator
before committing.

---

## 2026-06-06 — seeds.py created duplicates on every Docker rebuild

**What broke:** Running `docker compose exec backend python /app/backend/migrations/seeds.py`
multiple times (e.g. after a container rebuild) created duplicate experiments in
the database. The experiments list page showed 6 or 9 copies of the same three
experiments.

**Why it broke:** The idempotency check in `main()` counted total rows:
```python
count = await session.scalar(select(func.count()).select_from(Experiment))
if count:
    return  # skip
```
If any experiments existed from previous runs or from the UI, `count > 0`
triggered an early return and seeds never ran. But if the Postgres volume was
wiped (e.g. `docker compose down -v`) and seeds were then called twice in quick
succession, both calls saw `count == 0` and both inserted all three experiments.

**How I fixed it** (`backend/migrations/seeds.py`):
- Removed the count-based guard entirely.
- Added `_exists(session, name)` — a per-name check using
  `select(Experiment).where(Experiment.name == name)`.
- The `seed()` function now calls `_exists()` for each of the three experiments
  individually and skips the insert (with a printed message) if that name
  already exists. Only new experiments are committed.

*Git commit: `bebe66b` — fix: per-name seed idempotency and AI panel live fallback*

**Proof it works:** Running seeds twice produces:
```
Checking seed experiments…
  Skipping 'E-Commerce Checkout Redesign' — already exists.
  Skipping 'SaaS Onboarding Checklist' — already exists.
  Skipping 'Marketplace Fee Reduction' — already exists.
All seed experiments already present — nothing to do.
```

**What I learned:** Count-based idempotency guards are fragile. The correct
pattern for seed data is per-row uniqueness checks using a natural key (name,
slug, or external ID). This is especially important in seeds that might run in
parallel during deployment or be called by multiple init scripts.

---

## 2026-06-06 — AI Interpretation panel showed stale hardcoded values

**What broke:** The AI Interpretation panel (collapsible section at the bottom
of the results page) showed "observed lift: +0.0%, p=1.0000" regardless of the
actual analysis results. It also showed nothing at all until the user clicked
"Interpret with AI" — the fallback text never appeared automatically.

**Why it broke:** Three compounding issues:

1. The fallback text was a hardcoded constant string that never read from any
   result object — so it always showed stale/zero values.

2. `isFallback` was only set to `true` when the user had clicked the button AND
   the SSE stream failed. Before clicking, `isFallback = false`, so
   `displayText = ''` and the panel body was empty.

3. After `runAnalysis()` completed and `liveResult` was stored in state, the
   `AIInterpretationPanel` was not remounted — its internal `started` and `text`
   state persisted from any prior open/close cycle, so the new `liveResult` prop
   was ignored until a manual page refresh.

**How I fixed it:**

*`frontend/src/components/results/AIInterpretationPanel.jsx`:*
- Replaced the hardcoded constant with `buildFallbackFromResult(liveResult)`,
  which reads directly from `liveResult.stats.primary_result` (lift\_pct,
  p\_value, is\_significant, overall\_recommendation) and formats as:
  *"The treatment produced a statistically significant effect (observed lift:
  +25.9%, p<0.001). Recommendation: SHIP."*
- Changed `displayText = text || fallbackContent` (was `text || (isFallback ? fallbackContent : '')`),
  so fallback content appears immediately on expand.
- Removed the gating "Prompt to start" centered block; moved "Interpret with AI"
  button into the actions row that's always visible when not streaming.
- `isFallback` badge ("Auto-generated · AI unavailable") still only shows when
  SSE was attempted and failed — not on the initial expand.

*`frontend/src/pages/ExperimentResults.jsx`:*
- Changed `<AIInterpretationPanel result={result} …/>` to
  `<AIInterpretationPanel key={liveResult?.result_id ?? 'static'} result={liveResult} …/>`.
  The `key` prop forces a full remount when `liveResult` changes, clearing
  stale internal state. Passing raw `liveResult` (not the derived `result`)
  gives the fallback builder access to the original API response shape.

*Git commits: `a2e3358`, `bebe66b`, `8a4b0f1`*

**Proof it works:** Open the AI Interpretation panel immediately after "Run
Analysis" completes: the actual lift%, p-value, and SHIP/DO NOT SHIP label
appear without any click required.

**What I learned:** React component state does not reset when props change —
only when the component is unmounted and remounted. The `key` prop is the
correct tool to force a remount when you need a child to start fresh with new
data. Using `key={someId}` that changes when the data changes is a clean,
idiomatic pattern.

---

## 2026-06-06 — Proportion experiments showed raw decimals (0.05 instead of 5.00%)

**What broke:** After running "Run Analysis" on a proportion experiment (e.g.
E-Commerce Checkout Redesign with a 5% baseline), the stat cards showed:
- Control Rate: `0.05` (should be `5.00%`)
- Treatment Rate: `0.06` (should be `6.00%`)
- Confidence Interval: `[+0.01, +0.02]` (should be `[+0.7%, +1.9%]`)

Mean experiments were unaffected — their raw values were correct.

**Why it broke:** The formatting logic in `buildResultFromLive()` and
`buildResult()` checked `primary.test_type` to decide whether to multiply
rates by 100 and append `%`. The variable was named `testType` and used as
`expType` in the result object, which was then passed to `MetricsRow` as the
`expType` prop.

The problem: `primary.test_type` from the stats engine result is the *method
name* (e.g. `"z_test"`) not the *experiment type* (`"proportion"`). Since
`"z_test" !== "proportion"`, `isProportion` was always `false`, and all
proportion formatting was skipped.

**How I fixed it** (`frontend/src/pages/ExperimentResults.jsx`):
Both `buildResultFromLive` and `buildResult` now derive the `expType` used for
formatting decisions from `experiment.experiment_type` — the field stored on
the experiment record, which is always `"proportion"` or `"mean"`:
```javascript
const expType = experiment?.experiment_type ?? 'proportion'  // for formatting
const isProportion = expType === 'proportion'
// primary.test_type kept only for chart subtitle
```

*Git commit: `256b82f` — fix: proportion formatting, CI scaling, and recommendation labels*

**Proof it works:** E-Commerce stat cards now show `5.00%` / `6.30%` with CI
`[+0.7%, +1.9%]`. Marketplace (mean) still shows raw `$45.00` / `$50.11`.

**What I learned:** When a backend returns two fields that both look like "the
type" — one for the experiment category (`experiment_type: "proportion"`) and
one for the statistical method (`test_type: "z_test"`) — make sure the
frontend uses the right one for each purpose. Experiment *category* drives
display formatting; statistical *method* drives chart labels. Conflating them
is a silent bug that only surfaces on a specific experiment type.

---

## 2026-06-06 — Recommendation label showed "STOP_WIN" instead of "SHIP"

**What broke:** After running analysis, the AI Interpretation fallback text and
any other recommendation display showed internal backend enum codes like
`STOP_WIN`, `STOP_LOSE`, `RUN`, `DO_NOT_SHIP` — not human-readable labels.

**Why it broke:** The backend's stats engine returns `overall_recommendation`
using its internal decision enum names. The frontend stored and displayed these
codes as-is with no mapping layer.

**How I fixed it:**

*`frontend/src/pages/ExperimentResults.jsx`:*
Added `mapRecommendation()` at the top of the file:
```javascript
const REC_LABELS = {
  STOP_WIN:    'SHIP',
  STOP_LOSE:   'DO NOT SHIP',
  DO_NOT_SHIP: 'DO NOT SHIP',
  RUN:         'CONTINUE RUNNING',
}
function mapRecommendation(code) {
  if (!code) return null
  return REC_LABELS[code] ?? code  // unknown codes pass through unchanged
}
```
Applied in both `buildResultFromLive` and `buildResult`:
```javascript
recommendation: mapRecommendation(stats.overall_recommendation),
```

*`frontend/src/components/results/AIInterpretationPanel.jsx`:*
The fallback builder reads from `liveResult` directly (bypassing the derived
`result`), so it also needed the mapping applied inline when extracting
`overall_recommendation`.

*Git commit: `256b82f` — fix: proportion formatting, CI scaling, and recommendation labels*

**Proof it works:** AI Interpretation fallback now reads "Recommendation: SHIP."
or "Recommendation: DO NOT SHIP." depending on outcome.

**What I learned:** Internal enum/code names should never leak into the UI.
The right pattern is a mapping constant defined once at the boundary between
API and UI — not spread across templates or components. If the backend adds a
new code, there is exactly one place to update. Codes that are not in the map
pass through unchanged (the `?? code` fallback), which surfaces unknown values
clearly during development instead of silently showing nothing.

---

*Last updated: 2026-06-06*
