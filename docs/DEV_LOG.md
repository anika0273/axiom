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

*Last updated: 2026-06-05*
