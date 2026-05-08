# Intelligence Layer — Explainers

Five AI functions sit between raw statistical results and the humans who act on them.
Each is independently deployable: a failure in one never blocks the others.

---

## 1. Experiment Planner (`planner.py`)

**What it does:** Converts a free-text experiment description into a statistically
validated plan — metric type, MDE, sample size, runtime, risks, and guardrail metrics.

**Inputs**
- `description` — free-text description of the experiment (max 2 000 chars)
- `context` — optional dict, e.g. `{"daily_traffic": 1500}`
- `db` — async SQLAlchemy session for audit logging (may be `None` in tests)

**Outputs** (`ExperimentPlanResult`)

| Field | Type | Notes |
|---|---|---|
| `plan` | `ExperimentPlan \| None` | `None` when clarification is needed |
| `needs_clarification` | `bool` | True → ask the questions below first |
| `clarifying_questions` | `list[str]` | Specific missing info Claude surfaced |
| `confidence` | `"high" \| "medium" \| "low"` | Based on completeness of input |
| `confidence_reasoning` | `str` | One sentence explaining the rating |
| `stats_engine_verification` | `SampleSizeResult \| None` | Stats engine output, not Claude's |
| `prompt_version` | `str` | e.g. `"planner_v1"` — logged to DB |

**How confidence is determined**
- `high` — baseline rate and daily traffic both provided; metric type unambiguous
- `medium` — one number is inferred (e.g. MDE from stated business goal)
- `low` — baseline or metric type is missing; Claude had to guess

Claude sets the initial confidence value. The planner then *downgrades* it if
`validate_plan()` finds structural errors in the returned plan.

**Failure / fallback**
If the Claude API times out or returns an unexpected response, `plan_experiment`
calls `fallback_plan(description)` and returns an `ExperimentPlanResult` with
`needs_clarification=True`, six standard clarifying questions, and `confidence="low"`.
The caller receives a valid object with no exception raised.

**Interview Q&A**

*Q: How does the planner ensure Claude never invents a sample size?*

A: The `create_experiment_plan` tool schema deliberately omits `sample_size_per_group`
as an output field — Claude has no slot to put a number in. After Claude returns,
`_run_stats_verification()` calls `calculate_sample_size()` from the stats engine
using Claude's extracted baseline and MDE. That function's output is the sole source
of sample-size truth. If baseline or MDE is missing, sample size is `None` — never
fabricated.

---

## 2. Results Interpreter — Streaming (`interpreter.py`)

**What it does:** Streams a plain-English interpretation of completed experiment
results — combining statistical significance, lift, ML validity verdict, and HTE
findings — directly to the browser via Server-Sent Events.

**Inputs**
- `stats_result: FullAnalysisResult` — significance, p-value, lift_pct, lift_abs, recommendation
- `ml_result: MLAnalysisSummary` — overall_verdict, novelty_pattern, top HTE modifier, segment data
- `experiment_name: str` — sanitized before inclusion in the prompt
- `daily_traffic: int | None` — optional context (not used statistically)

**Outputs**
An `AsyncGenerator[str, None]` — yields text chunks as they arrive from the Claude
stream. Callers collect chunks into an SSE response. After the stream closes, the
interpreter runs a grounding validator and `OutputValidator` on the assembled text.

**How confidence is determined**
There is no explicit confidence field here. Instead, the prompt injects all numerical
values verbatim and instructs Claude to use them exactly. The post-stream
`_validate_grounding()` function checks:
- Any `%` mention differing by more than 2 pp from `lift_pct` → `WARNING` log
- Recommendation of "ship" when `is_significant=False` → `WARNING` log

Logged warnings are advisory; they do not halt the stream.

**Failure / fallback**
If the Claude stream raises at any point, the generator:
1. Emits a separator line if any chunks were already sent
2. Calls `build_fallback_interpretation(stats_result, ml_result)` — a pure template
   function that uses only the actual statistical values, never fabricates numbers
3. Yields the fallback text as a single chunk

The browser receives *something* in all cases.

**Interview Q&A**

*Q: How do you prevent Claude from hallucinating lift numbers in the interpretation?*

A: The user prompt injects every numerical value with explicit labels:
`lift_pct (relative lift): +15.2000%`. The system prompt instructs Claude to use
those exact values and never invent others. Post-stream, `_validate_grounding()`
scans the assembled text for any percentage that differs by more than 2 pp from the
actual lift and logs a warning. The template fallback uses no Claude at all — it
formats the raw numbers directly into sentences.

---

## 3. Stakeholder Report Writer (`reporter.py`)

**What it does:** Produces an 8-section executive-ready report from experiment results.
Sections 1–7 are written by Claude in plain English; Section 8 (Technical Appendix)
is always programmatic and injects the raw p-value, lift, confidence intervals, and
ML verdict.

**Inputs**
- `experiment_name: str`
- `stats_result: FullAnalysisResult`
- `ml_result: MLAnalysisSummary`
- `daily_traffic: int | None`
- `daily_revenue: float | None` — used in Section 2 (Business Impact) to estimate revenue delta
- `db` — async session for logging

**Outputs** (`StakeholderReport`)

| Field | Type |
|---|---|
| `sections` | `list[ReportSection]` — exactly 8 items |
| `recommendation` | `"SHIP" \| "EXTEND" \| "STOP" \| "INVESTIGATE"` |
| `prompt_version` | `str` — e.g. `"reporter_v1"` |
| `generated_at` | `datetime` |

Each `ReportSection` has `number`, `title`, `content`, and `is_programmatic`.

**Section titles**

| # | Title |
|---|---|
| 1 | Executive Summary |
| 2 | Business Impact |
| 3 | What We Tested |
| 4 | Results |
| 5 | Who It Worked For |
| 6 | Concerns |
| 7 | Recommendation |
| 8 | Technical Appendix |

**How confidence is determined**
The reporter does not expose a confidence field. Instead, `OutputValidator.validate_report()`
runs after Claude's tool_use call and enforces safety invariants:
- `SHIP` when `is_significant=False` → auto-corrected to `EXTEND`
- `SHIP` when `can_trust_results=False` → auto-corrected to `INVESTIGATE`
- Statistical jargon in sections 1–7 → `WARNING`
All corrections are logged at `WARNING` level before the report is returned.

**Failure / fallback**
If the Claude API fails, `build_fallback_report()` generates all 8 sections from
templates using the actual statistical values. Every section is labelled
`[Auto-generated — AI unavailable]`. The returned `StakeholderReport` has
`prompt_version` ending in `_fallback`.

**Interview Q&A**

*Q: Why is Section 8 always programmatic rather than written by Claude?*

A: Section 8 (Technical Appendix) contains the authoritative statistical numbers —
p-value, confidence intervals, sample sizes, ML verdict. Allowing Claude to generate
this section would introduce the risk of hallucinated values in the one place where
precision is non-negotiable. Stakeholders who understand statistics go straight to
Section 8; it must be bit-for-bit identical to what the stats engine computed.

---

## 4. Guardrails System (`guardrails.py`)

**What it does:** Four cooperating classes that make every Claude call safe:
`InputGuardrail` sanitizes user text before it reaches Claude;
`OutputValidator` checks and auto-fixes Claude responses;
`RateLimiter` enforces per-session call budgets;
`ClaudeCallWrapper` adds retry, per-attempt timeout, and fallback routing.

**Inputs / Outputs by class**

| Class | Primary input | Primary output |
|---|---|---|
| `InputGuardrail.sanitize(text, max_chars)` | Raw user text | `SanitizeResult` — cleaned text + rejection reason |
| `OutputValidator.validate_plan(plan, stats)` | Tool output dict | `ValidationReport` — issues + requires_fallback flag |
| `OutputValidator.validate_interpretation(text, stats)` | Assembled stream text | `ValidationReport` — grounding warnings |
| `OutputValidator.validate_report(report, stats)` | Tool output dict | `ValidationReport` — auto-fixed recommendation |
| `RateLimiter.check(session_id, max_calls, window_s)` | Session ID | `RateLimitResult` — allowed bool + remaining |
| `ClaudeCallWrapper.call_with_retry(func, ...)` | Async callable | `(result, used_fallback)` tuple |

**How confidence is determined**
The guardrails do not produce confidence scores. They produce pass/fail verdicts and,
for `OutputValidator`, severity-labelled issues (`"error"` blocks, `"warning"` advises).
`validate_report` is the only place auto-fixes occur — it mutates the report dict
in-place and logs every correction.

**`InputGuardrail` detection order**
1. Length check — reject if `len(text) > max_chars`
2. Injection patterns — case-insensitive substring match against 8 known phrases
   (`"ignore previous instructions"`, `"act as"`, `"jailbreak"`, etc.)
3. Control character strip — remove `\x00–\x1f` except `\n` and `\t`
4. Whitespace collapse — merge runs of spaces, strip edges

Steps 1–2 are hard rejections (return early with `rejection_reason`).
Steps 3–4 are silent cleanups (`was_modified=True`, `rejection_reason=None`).

**Failure / fallback**
`InputGuardrail` and `OutputValidator` are pure functions with no I/O — they cannot
fail. `RateLimiter` uses only in-memory state under a threading lock. The wrapper's
fallback path is invoked when all retries are exhausted; if the fallback itself
raises, `(None, True)` is returned — never a propagated exception.

**Interview Q&A**

*Q: What happens if an attacker sends "IGNORE PREVIOUS INSTRUCTIONS" in all-caps?*

A: `InputGuardrail.sanitize` converts the text to lowercase before checking
injection patterns (`lower = text.lower()`), so case variation is irrelevant.
The match is a substring check — any text containing the pattern, regardless of
surrounding words, is rejected with a specific `rejection_reason` that identifies
which pattern was matched.

---

## 5. Fallback Chain (`fallbacks.py` + `templates/`)

**What it does:** Guarantees that the intelligence layer always returns a
structurally valid, grounded response even when the Claude API is completely
unavailable. Three fallback functions — one per AI module — produce template-based
outputs using only the actual statistical values passed in.

**Inputs / Outputs**

| Function | Input | Output |
|---|---|---|
| `fallback_plan(description)` | Raw description string | `dict` compatible with `ExperimentPlanResult` fields |
| `fallback_interpretation(stats, ml)` | `FullAnalysisResult`, `MLAnalysisSummary` | Plain-text string |
| `fallback_report(stats, ml, name, ...)` | Both result types + experiment name | Full `StakeholderReport` (8 sections) |

**How confidence is determined**
All fallbacks return `confidence="low"` or equivalent indicators. `fallback_plan`
returns `needs_clarification=True` with the six standard questions — it never
produces a plan. `fallback_interpretation` and `fallback_report` use `FullAnalysisResult`
values (significance, lift, p-value) to pick appropriate template phrases — they
never fabricate numbers. Every output is prefixed with `[Auto-generated — AI unavailable]`.

**Fallback trigger points**

| Trigger | Which fallback fires |
|---|---|
| `ClaudeCallWrapper` exhausts retries | Caller checks `used_fallback=True` and calls the appropriate function |
| Claude returns no `tool_use` block | `plan_experiment` / `generate_report` call their fallback directly |
| `OutputValidator.requires_fallback=True` | `plan_experiment` calls `fallback_plan` |
| Stream raises mid-generation | `interpret_results` generator yields fallback text inline |

**Why templates instead of cached responses**
Cached responses are snapshots — they would show a lift from a *different* experiment.
Templates are parameterized with the actual result values, so the output is always
numerically correct for the current experiment, even when Claude is unreachable.

**Interview Q&A**

*Q: How do you ensure fallback text is never mistaken for real AI output?*

A: Every fallback function prepends the literal string `[Auto-generated — AI unavailable]`
before any content. The calling API endpoint propagates this through the response
envelope as-is — the frontend renders it as a distinct "AI unavailable" state rather
than an AI-generated summary. Additionally, `StakeholderReport` has a `prompt_version`
field ending in `_fallback` when the fallback path was used, allowing the database
audit trail to distinguish template-generated reports from Claude-generated ones.
