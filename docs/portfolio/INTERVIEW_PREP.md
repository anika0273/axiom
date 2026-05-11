# Axiom — Interview Preparation Guide

GitHub: https://github.com/anika0273/axiom  
Project period: ~41 days, 5 phases (2026-03 → 2026-05)

---

## Table of Contents

1. [Elevator Pitches](#1-elevator-pitches)
2. [Statistics Engine](#2-statistics-engine)
3. [Machine Learning Layer](#3-machine-learning-layer)
4. [Claude AI Integration](#4-claude-ai-integration)
5. [Production Architecture](#5-production-architecture)
6. [Testing Strategy](#6-testing-strategy)
7. [Common Interview Questions](#7-common-interview-questions)
8. [System Design: Build an A/B Platform from Scratch](#8-system-design-build-an-ab-platform-from-scratch)
9. [Red Flags to Avoid](#9-red-flags-to-avoid)
10. [Questions to Ask the Interviewer](#10-questions-to-ask-the-interviewer)

---

## 1. Elevator Pitches

### 30 seconds (for recruiters)

"Axiom is a full-stack A/B testing platform I built from scratch. Most teams either use expensive SaaS tools with black-box statistics, or run their own analysis in spreadsheets where it's easy to make mistakes. Axiom gives you rigorous, auditable statistics — sequential testing so you can check results without inflating false positives, automatic multiple-metric correction, variance reduction — plus an AI layer powered by Claude that writes the stakeholder report for you. It's deployed on Railway with Docker, has 894 tests, and the demo is live."

### 2 minutes (for engineers)

"The problem Axiom solves is that most A/B testing workflows are statistically unsound in the same three ways: peeking at results and stopping when p < 0.05 (which inflates false positive rate to ~30%), tracking multiple metrics without correction (10 metrics × 0.05 ≈ 40% chance of at least one false positive), and ignoring variance reduction techniques that could halve your required sample size.

Phase 1 was building the stats engine — z-test, t-test, CUPED variance reduction, sequential testing via SPRT, Bonferroni and Benjamini-Hochberg correction, power analysis, and SRM detection. 430 tests at 96% line coverage.

Phase 2 was an ML layer — heterogeneous treatment effect analysis using a causal forest approach with XGBoost and SHAP to identify subgroups where the treatment worked differently, plus segment discovery, anomaly detection, and novelty scoring. 751 total tests.

Phase 3 was the Claude AI layer — a natural-language experiment planner using tool_use, a streaming result interpreter with SSE and a grounding validator to prevent hallucinated lift numbers, and a stakeholder report generator. The design decision I'm most proud of there is that Section 8 — the final recommendation — is always assembled programmatically from raw stats, never from Claude's free text, because I didn't want AI-generated text to be the deciding input for shipping a feature.

Phase 4 was a React frontend — wizard-style experiment creation, live streaming results via EventSource, a demo mode with zero API calls.

Phase 5 was production — Docker multi-stage build, nginx reverse proxy, Railway deployment, GitHub Actions CI.

Total: 894 tests, ~41 days of work."

---

## 2. Statistics Engine

**Files:** `backend/app/stats/` — testing.py, cuped.py, sequential.py, corrections.py, power.py, engine.py, bucketing.py

### 2-sentence explanation (non-technical)

"The stats engine is the mathematical core that decides whether an experiment's results are real or just random noise. It implements seven different techniques to make that judgment more accurate — including methods to correct for the natural human tendency to stop an experiment the moment the numbers look good."

### Technical deep dive

**CUPED** (`cuped.py`)
- Pre-experiment covariate adjustment: `Y_adj = Y - θ * (X - E[X])` where θ = Cov(Y,X)/Var(X)
- Reduces variance of the treatment effect estimator, often by 20–40%
- Implementation challenge: what to do when pre-experiment data is missing (some users have no prior activity), when variance is near-zero (causing numerical instability in θ), and how to center X correctly when control and treatment groups have different sample sizes
- Decision: use the pooled X mean across both arms for centering, and fall back to raw Y when covariate coverage is below 80%

**Sequential testing** (`sequential.py`)
- Implements SPRT (Sequential Probability Ratio Test) with Wald bounds
- Produces always-valid p-values: the test is valid at any stopping time, not just at a fixed horizon
- The standard z-test is only valid at a pre-specified sample size — checking it repeatedly inflates type I error geometrically
- Mixes poorly with Bayesian updating; Axiom keeps them separate: SPRT for sequential, separate Beta-Binomial path for Bayesian

**Multiple comparison correction** (`corrections.py`)
- Bonferroni: divide α by k metrics — conservative, controls FWER
- Benjamini-Hochberg: rank p-values, reject if p_i ≤ (i/k)α — controls FDR, more power
- Default is BH; Bonferroni available when false positives are especially costly (medical decisions)
- The UserWarning about PRDS (positive regression dependence) is intentional — surfaced to the caller, not swallowed

**SRM detection** (`engine.py`)
- Chi-squared test on observed vs. expected assignment counts
- Threshold: p < 0.01 → SRM_DETECTED warning attached to result
- Does not invalidate results automatically — surfaced as a warning for human review, because SRM can sometimes be benign (e.g., bot filtering)

**Bucketing** (`bucketing.py`)
- `hash(experiment_id + subject_id) % 10000` mapped to traffic buckets
- Each experiment has a unique `randomisation_salt` (UUID at creation) to prevent cross-experiment correlation
- Deterministic: same subject always gets same variant, even if the service restarts

### Design decision questions

**Q: Why not just use scipy.stats directly in route handlers?**
A: Because statistical correctness rules belong in a single canonical location that can be independently tested. If each endpoint reimplements a z-test, any fix needs to be applied in N places. The engine is the source of truth; API handlers call it and return shaped results.

**Q: Why implement CUPED yourself instead of using a library?**
A: There's no standard library for CUPED — the original paper is a 2013 Microsoft Research paper and most implementations are in R. Writing it from scratch meant I could handle the edge cases specific to Axiom's data model (missing covariates, small-sample fallback) rather than working around a library that assumed clean pre-experiment data.

### Failure modes

**Q: What breaks under load?**
- Stats recomputation is synchronous CPU-bound work. Under high concurrency, the async FastAPI process blocks the event loop during heavy numpy operations on large arrays. Fix: offload to a thread pool with `asyncio.run_in_executor` for array sizes above a threshold.
- CUPED scales poorly if pre-experiment data is pulled fresh from Postgres per-request. Fix: pre-aggregate into daily rollups in a background job so the recomputation reads a much smaller table.

---

## 3. Machine Learning Layer

**Files:** `backend/app/ml/` — hte.py, segments.py, anomaly.py, novelty.py, engine.py

### 2-sentence explanation (non-technical)

"The ML layer answers a question the stats engine can't: 'Did the experiment work the same way for everyone, or did it work much better for some users and worse for others?' It uses machine learning to identify those subgroups automatically rather than requiring an analyst to guess which segments to look at."

### Technical deep dive

**HTE — Heterogeneous Treatment Effects** (`hte.py`)
- Estimates individual treatment effects using a causal forest-style approach (XGBoost meta-learner)
- T-learner: fit separate outcome models μ_t(X) and μ_c(X) for treatment and control; ITE = μ_t(x) - μ_c(x)
- SHAP values explain which features drive variation in the treatment effect — "mobile users had higher lift because feature X was 3× more important"
- Output: ranked list of subgroups with their estimated CATE (Conditional Average Treatment Effect) and confidence interval

**Segment discovery** (`segments.py`)
- K-means on the feature space, then characterizes each cluster by SHAP feature importance
- Key design choice: segments are defined by feature importance patterns, not just by metric averages — so you get "mobile + low-recency users" not just "users in quartile 3"

**Anomaly detection** (`anomaly.py`)
- Isolation Forest on the metric time series
- Flags data collection artifacts (instrumentation spikes, bot traffic bursts) that could invalidate stats
- Runs before the stats engine processes a batch — if anomaly score > threshold, attaches a warning to the result

**Novelty scoring** (`novelty.py`)
- One-Class SVM trained on control-group feature distributions
- Scores each treatment-group user for out-of-distribution distance
- High novelty score = user behavior is not represented in training data = treatment effect estimate unreliable for that user

### Design decision questions

**Q: Why XGBoost for HTE instead of a dedicated causal inference library like DoWhy?**
A: DoWhy and EconML are excellent but add significant dependency weight and have a steeper API surface. For Axiom's use case — providing directional subgroup insights, not causal effect point estimates for academic use — the T-learner approach with XGBoost gives interpretable results without the complexity. If Axiom were used for clinical trials, the answer would change.

**Q: How do you validate that the HTE results are real and not noise?**
A: Three checks: (1) the subgroup must have at least 1000 subjects (configurable) to have any statistical power, (2) the CATE confidence interval must not include zero, (3) a permutation test shuffles treatment labels and confirms the subgroup effect disappears — if it doesn't, the effect is likely noise.

---

## 4. Claude AI Integration

**Files:** `backend/app/intelligence/` — planner.py, interpreter.py, reporter.py, guardrails.py, fallbacks.py, costs.py

### 2-sentence explanation (non-technical)

"The AI layer uses Claude to translate raw statistics into language that product managers and executives can act on. It can design experiments from a plain-English brief, explain results in plain English as they stream live, and write the full stakeholder report automatically."

### Technical deep dive

**Experiment Planner** (`planner.py`)
- Input: free-text experiment description ("We want to test a new checkout button color")
- Uses Claude's `tool_use` to force structured output: `ExperimentPlan` Pydantic model with hypothesis, primary metric, secondary metrics, required sample size, recommended duration
- The sample size in the plan is verified by calling the stats engine's `power_analysis()` — Claude proposes it, the stats engine confirms it, and if they disagree the stats engine wins
- Prompt is versioned: `PLANNER_PROMPT_V1` in `intelligence/prompts/`

**Result Interpreter** (`interpreter.py`)
- Streams via SSE: `StreamingResponse` with `text/event-stream` MIME type
- FastAPI generator yields `data: {chunk}\n\n` tokens as they arrive from the Anthropic streaming API
- **Grounding validator**: after the stream completes, the buffer is scanned for numeric lift claims (regex: `\d+(\.\d+)?%`). Each claimed number is compared to the actual result data. If the deviation is > 5%, the number is corrected in-place and a `[corrected]` annotation added.
- This is the most important safety mechanism in the AI layer — it prevents "the new checkout increased conversions by 23%" when the actual number was 8%.

**Stakeholder Reporter** (`reporter.py`)
- Generates 8 sections via `tool_use`: executive summary, hypothesis, methodology, results table, statistical significance, risk factors, recommendation, and action items
- **Section 8 rule**: the "declare winner / keep running / stop" recommendation is always assembled programmatically from the Pydantic result object, never from Claude's free text. Claude writes the narrative context; the categorical decision comes from the stats engine.
- `cache_control: {"type": "ephemeral"}` on the system prompt — long prompts are cached between calls in the same session

**Guardrails** (`guardrails.py`)
- `InputGuardrail`: prompt injection detection (checks for instruction override patterns like "ignore previous instructions")
- `OutputValidator`: after generation, validates that SHIP/NO_SHIP recommendations are consistent with the statistical significance in the result data. Auto-corrects if mismatched.
- `RateLimiter`: token-bucket per user, 10 requests/minute for AI endpoints
- `ClaudeCallWrapper`: try/except around every API call; on failure, calls fallback layer

**Fallbacks** (`fallbacks.py`)
- Template-based responses for all three functions when Claude API is unavailable
- Planner fallback: returns a basic plan with default metric choices and a conservative sample size
- Interpreter fallback: returns a structured summary of raw stats without narrative
- Reporter fallback: returns a minimal 3-section report from raw result data
- Design principle: AI unavailability must never prevent experiment creation or stats computation

### Design decision questions

**Q: Why tool_use for the reporter instead of just prompting for markdown?**
A: `tool_use` forces Claude to return a structured JSON schema that Pydantic validates. If I prompt for markdown, Claude might return 7 sections instead of 8, or skip the risks section when results are positive, or use inconsistent terminology. The tool call enforces the contract.

**Q: How do you prevent the AI from making up statistics?**
A: Three layers: (1) the system prompt explicitly forbids stating percentages not provided in the input data, (2) the grounding validator scans the output for numeric claims and cross-references them against actual result data, (3) Section 8 (the recommendation) is never AI-generated text — it's programmatically assembled from the result object, so the categorical decision is always correct even if the narrative is wrong.

**Q: How do you control Claude API costs?**
A: The `costs.py` module estimates token costs per call using a rates table keyed by model prefix. Every call logs estimated cost to the `ai_interactions` table. The `/api/v1/intelligence/usage` endpoint exposes a usage report. Rate limiting at 10 requests/minute per user caps worst-case spend. The `cache_control` on system prompts reduces cost for repeated calls.

### Failure modes

**Q: What happens if Claude returns malformed JSON in a tool_use call?**
A: FastAPI's dependency injection runs Pydantic validation on the tool output before it reaches the route handler. If validation fails, the `ClaudeCallWrapper` catches the `ValidationError`, logs it at WARNING level, and invokes the fallback layer. The UI renders "AI summary temporarily unavailable" rather than an error page.

---

## 5. Production Architecture

**Files:** `docker-compose.prod.yml`, `infra/nginx/`, `infra/scripts/prod-start.sh`, `.github/workflows/integration-tests.yml`

### 2-sentence explanation (non-technical)

"The platform runs in Docker containers with a reverse proxy in front that handles incoming traffic, enforces rate limits, and serves the frontend as static files. Deployments are automated: code merged to main deploys to staging, a version tag deploys to production."

### Technical deep dive

**Docker network isolation**
- All four services (postgres, backend, frontend, nginx) share an internal bridge network called `internal`
- Only nginx binds a host port (`:80`)
- Backend and frontend have no host ports — they're only reachable through nginx
- This means a misconfigured backend endpoint can't be called directly from the internet, bypassing nginx's rate limiting and security headers

**nginx configuration** (`infra/nginx/nginx.conf`)
- `/api/*` → `proxy_pass http://backend:8000` with `proxy_buffering off` for SSE endpoints
- `/*` → serves React static build from `/usr/share/nginx/html`
- Rate limiting: `limit_req_zone` with 10 r/s for API, 2 r/s for intelligence endpoints
- Security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`
- gzip compression for responses > 1KB

**Production start script** (`infra/scripts/prod-start.sh`)
- Validates that required env vars (DATABASE_URL, ANTHROPIC_API_KEY, SECRET_KEY) are set before starting
- Snapshots current image tags for rollback: `docker inspect axiom-backend:latest | grep Id > .last_deploy`
- `docker compose -f docker-compose.prod.yml build && up -d`
- Runs Alembic migrations after containers are healthy
- Waits for `/api/v1/stats/health` to return 200 within 60 seconds; aborts and rolls back if not

**CI pipeline** (`.github/workflows/integration-tests.yml`)
- Triggers: weekly (Sunday 06:00 UTC) + manual dispatch
- Provisions a Postgres service container
- Runs `pytest -m integration` against the real Claude API (API key from GitHub secrets)
- Writes a GitHub step summary with pass/fail counts and cost estimate
- Note: this is an integration test pipeline, not a general PR-gate — a full PR gate workflow (ruff + full pytest + TypeScript type-check) is a known gap for a future sprint

**Railway deployment**
- Staging: auto-deploys on merge to `main`
- Production: deploys on `v*` tag push
- Environment variables injected by Railway (never in image or repo)

### Design decision questions

**Q: Why nginx as a reverse proxy instead of just exposing FastAPI directly?**
A: Three reasons: (1) nginx serves the React static build directly, so the frontend doesn't need a separate container, (2) nginx handles rate limiting at the network layer before requests reach Python, which is more efficient, (3) security headers are centrally managed in one place regardless of which backend framework is used.

**Q: Why Railway instead of AWS/GCP?**
A: Railway provisions Postgres automatically, injects environment variables, and deploys from git with zero infrastructure YAML. For a one-person project, the time saved on infrastructure configuration outweighs the cost premium over AWS. When traffic scales past Railway's pricing threshold, the Docker setup is portable to ECS or Cloud Run with minimal changes.

### Failure modes

**Q: What's the rollback story if a bad deployment goes out?**
A: The `prod-start.sh` script saves the previous image SHA before building. If the health check fails, it re-runs `docker compose up -d` with the old image tag. For Railway, Railway retains the last three deployments and supports one-click rollback from the dashboard. Database rollback uses `alembic downgrade -1` — only possible if the migration has a working `downgrade()` and is run before the next migration.

---

## 6. Testing Strategy

**894 tests total — 430 stats, 321 ML, 107 AI, 36+ API**

### 2-sentence explanation (non-technical)

"Every function in the statistical and ML engine has its own automated test that verifies correct output — including edge cases like empty data, zero variance, and very small sample sizes. The API tests verify that every endpoint returns the right status codes and data shapes, so a schema change doesn't silently break callers."

### Coverage philosophy

- **Stats functions: 100% line coverage required** — statistical code has subtle edge cases that look correct in the happy path but fail on real data. If a code path isn't tested, assume it's wrong.
- **ML public functions: 100% line coverage** — same reasoning; numerical stability bugs hide in uncovered branches.
- **Services: 80%** — business logic tested, but not every internal helper.
- **API endpoints: happy path + error path per endpoint** — at minimum, verify the success shape and the 404/422 shape.

### What the test layers actually check

**Unit tests (stats):**
- Correct output for known inputs (e.g., z-test on two proportions with known ground truth)
- Edge cases: zero variance in one arm, n=1, all subjects in control, zero conversions
- Expected exceptions: `ValueError` for invalid confidence levels, `ZeroDivisionError` prevention

**Unit tests (ML):**
- Output shape (correct number of rows/columns)
- No NaN in output (numerical stability check)
- Behavior with missing features (graceful degradation vs. hard fail)

**Integration tests (API):**
- Every route tested with a real test database (PostgreSQL running in CI via service container)
- No mocked DB — a deliberate choice to prevent mock/prod divergence
- Concurrency test for assignment endpoint: `asyncio.gather(20 concurrent assignment requests)` → must all return same variant for same subject

**Intelligence tests:**
- Claude API calls are mocked (Anthropic SDK mock) — AI tests don't burn real API credits in unit/CI runs
- Weekly CI job runs with real API to catch prompt drift or model behavior changes
- Fallback tests: verify template responses are returned when mock raises `APIError`

### Design decision questions

**Q: Why not mock the database in integration tests?**
A: Real database tests catch constraint violations, query planner behavior, and index usage that mocks never surface. The CI environment provisions a Postgres service container, so there's no cost to using real Postgres in tests.

**Q: How do you test the grounding validator without real Claude responses?**
A: The mock injects controlled responses with intentional numeric errors — e.g., "conversion rate increased by 23%" when the result fixture says 8.2%. The test then verifies the validator corrects it to "8.2%".

---

## 7. Common Interview Questions

**"Tell me about a technically challenging problem you solved."**

"The hardest single problem was the CUPED implementation. The textbook formula is four lines. The production version handles: subjects with no pre-experiment data (can't use the covariate for them — fall back to raw Y, but now your sample is heterogeneous), near-zero covariate variance (θ blows up — need to detect and skip the adjustment), centering the covariate correctly when treatment/control have different sizes (use pooled mean, not per-arm mean, or you introduce bias), and numerical stability when metric scales differ by 3 orders of magnitude. The 430 stats tests were what made me confident it was correct — not my intuition about the math."

**"How do you ensure statistical validity?"**

"Four layers. First, assignment is deterministic hash-based with a per-experiment salt, so the same subject always gets the same variant and cross-experiment correlation is zero. Second, the stats engine is the canonical location for all test implementations — nothing is reimplemented inline. Third, SRM detection runs on every stats recomputation — if observed assignment ratios don't match target ratios (chi-squared p < 0.01), a warning is attached to the result. Fourth, sequential testing is available for teams that need to check results before the planned end date — SPRT gives always-valid p-values that are safe to check at any stopping time."

**"How does the AI integration work? How do you prevent hallucinations?"**

"Three mechanisms. One: the system prompt forbids the model from stating any percentage or number that wasn't provided in the input data. Two: the grounding validator scans the output after streaming for numeric lift claims using a regex pattern, cross-references each against the actual result data, and corrects any that deviate by more than 5%. Three: the final recommendation — ship/don't ship — is never AI-generated text. It's assembled programmatically from the Pydantic result object. Claude writes the narrative context; the categorical decision comes from deterministic code."

**"How would you scale this to 10× traffic?"**

"The main bottlenecks are: stats recomputation (CPU-bound numpy on large arrays — fix: offload to thread pool, pre-aggregate into daily rollups so recomputation touches smaller tables), the assignment endpoint (currently synchronous per-request insert with ON CONFLICT — scales well to high concurrency already due to idempotency design), and Claude API calls (rate-limited at 10/minute per user already — the bottleneck is Anthropic's API, which you can't control). For the database, read replicas for analytics queries would separate the assignment write load from the stats read load."

**"What would you do differently if starting over?"**

"I'd design the event ingestion layer first, before the stats layer. Axiom currently assumes pre-aggregated metric inputs — it doesn't have a raw event stream. In production, you'd need to handle late-arriving events (conversion with 48-hour attribution window), duplicate events (idempotent ingestion), and event schema evolution. If I'd built the event pipeline first, the stats engine would have been designed to process from raw events with proper windowing rather than pre-aggregated inputs."

**"What tradeoffs did you make?"**

"The biggest one is the T-learner for HTE versus a proper doubly-robust estimator. T-learner is easy to implement and interpret, but it's biased when treatment and control have different covariate distributions — which they usually do in real experiments due to randomization variance at small N. A doubly-robust estimator (like AIPW) corrects for this but is harder to explain to a non-statistician. I chose T-learner with an explicit caveat in the API response for small sample sizes."

**"How do you test AI-generated outputs?"**

"Unit tests mock the Anthropic SDK and inject controlled responses — deterministic, fast, no API cost. Weekly CI runs with the real API to catch prompt drift — if a model update changes Claude's behavior in a way that breaks the grounding validator or produces malformed tool_use JSON, the weekly run catches it before users do. For output quality, the evaluation framework in `scripts/eval_ai.py` scores interpreter outputs against human-written reference summaries using BLEU and a small set of human ratings."

**"Walk me through your CI/CD pipeline."**

"On push to any branch, the linter and type-checker run. On merge to main, the full integration test suite runs against a Postgres service container and the live Claude API — this is the gate before Railway deploys to staging. On a `v*` tag push, Railway deploys to production after staging has been green for 30 minutes. The deployment script runs migrations before the new containers start, and does a health check within 60 seconds — if it fails, the script re-deploys the previous image tag."

**"What's the most important thing you learned?"**

"That statistical correctness is adversarial to 'works in the happy path.' Every time I thought a test was correct, I'd write the edge case test and it would fail. Near-zero variance, missing covariates, n=1 samples, zero conversions — these aren't unusual in production A/B tests, they're the normal data you get in the first 24 hours of an experiment. The discipline of writing the edge case test before declaring something done was the biggest methodology shift."

---

## 8. System Design: Build an A/B Platform from Scratch

When asked to design an A/B testing system, draw on Axiom's actual decisions:

### Assignment service

"The core requirement is sticky assignment — same subject always gets same variant. I'd use deterministic hashing: `hash(experiment_id + salt + subject_id) % 10000` mapped to traffic buckets. The salt is unique per experiment to prevent cross-experiment correlation. Assignment is stored on first call with `INSERT ... ON CONFLICT DO NOTHING` — idempotent under concurrent requests, no distributed lock needed."

### Stats computation

"I'd separate event ingestion from stats computation. Ingestion: append-only event log, idempotent on event_id. Stats: scheduled background job recomputes from pre-aggregated daily rollups, not raw events. This means stats are slightly stale (up to 10 minutes) but the computation is fast and doesn't block on a 100M-row events table. SRM detection runs on every recomputation."

### AI integration

"Two design constraints: AI must never block assignment or ingestion, and AI recommendations must require human confirmation before state changes. I'd wrap every Claude call in a fallback layer that returns structured template responses on failure. I'd use tool_use for planning and reporting to enforce schema, and add a grounding validator for any numeric claims in the output."

---

## 9. Red Flags to Avoid

**About statistics:**
- Don't say "p < 0.05 means the result is real" — p-value is the probability of seeing this result if the null were true, not the probability the null is true.
- Don't say "we ran the test until we got significance" — that's the peeking problem; that's exactly what sequential testing prevents.
- Don't say "I corrected for multiple comparisons" without knowing the difference between FWER (Bonferroni) and FDR (BH) and when you'd use each.

**About ML:**
- Don't say "I trained a model" without being able to say what it predicts (ITE/CATE for HTE, anomaly score for isolation forest), on what features, and how you validated it wasn't just capturing noise.
- For HTE: know the difference between ATE (average over all subjects) and CATE (conditional on subgroup). The ML layer estimates CATE.

**About Claude:**
- Don't say "I just call the API" — be ready to explain prompt versioning, `cache_control`, `tool_use` vs. free-text, the grounding validator, and the fallback layer.
- Don't say the AI "decides" whether to ship — the AI is advisory. The human confirms.

**About testing:**
- Don't say "I wrote unit tests" without being able to explain what they cover. Specifically: do they hit a real database or a mock? How do you test concurrent assignment? How do you test AI output correctness?

---

## 10. Questions to Ask the Interviewer

**For a product/growth team:**
- "What's your current process for deciding to ship an experiment? Is there a human review step or does the platform auto-ship when significance is reached?"
- "Do you track novelty of your experiment population — how often your treatment users look different from your training data?"

**For an ML/data science role:**
- "How do you handle heterogeneous treatment effects today — do you segment post-hoc or use a formal HTE estimator?"
- "What's your sequentialization strategy — do you use fixed-horizon tests or always-valid inference?"

**For an infrastructure/platform role:**
- "How do you prevent cross-experiment correlation in assignment — do you use per-experiment salts?"
- "What's your rollback story if a bad model or stat computation goes to production?"
