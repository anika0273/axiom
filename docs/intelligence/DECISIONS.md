# Intelligence Layer — Design Decisions

Six decisions that shaped the Phase 3 architecture. Each decision had a viable
alternative; this document records what was chosen, why, and what it rules out.

---

## 1. Why `tool_use` instead of JSON mode for structured outputs?

**Decision:** The planner and reporter use `tool_choice={"type": "tool", "name": "..."}` to
force Claude to return a specific structured object. JSON mode (system prompt asking for
JSON + manual `json.loads`) was the alternative.

**Why tool_use wins here**

- **Schema enforcement.** The tool input schema specifies required fields, enum constraints
  (`"confidence": {"enum": ["high", "medium", "low"]}`), and type constraints
  (`"baseline": {"type": ["number", "null"]}`). Claude's tool_use layer enforces this
  before the response ever reaches Python. JSON mode gives you a string — you validate
  it yourself and handle all malformed cases.

- **No ambiguity about format.** With `tool_choice: {type: tool, name: create_experiment_plan}`,
  Claude has exactly one valid response shape. JSON mode allows Claude to wrap the JSON
  in markdown fences, add a preamble sentence, or return a differently-structured object
  — all of which require defensive parsing.

- **Field omission is explicit.** In the tool schema, `baseline` is typed `["number", "null"]`
  with the instruction "Set null if not stated — never estimate it." Claude returns `null`
  rather than fabricating a value. JSON mode gives no mechanism to enforce this at the
  model level.

- **Prompt caching is still available.** The system prompt containing all the planning
  instructions is marked for caching. tool_use doesn't preclude caching.

**What it rules out:** Tool use requires the response to be a single tool call. It can't be
combined with streaming (planner results are not streamed). For the interpreter, where
streaming is non-negotiable, tool_use is not used — plain text streaming is used instead.

---

## 2. Why streaming for interpretation but not for planning or reporting?

**Decision:** `interpret_results` is an `AsyncGenerator` that yields chunks from
`client.messages.stream(...)`. `plan_experiment` and `generate_report` use non-streaming
`client.messages.create(...)` with tool_use.

**Interpretation is long-form prose read in real time.** Users stare at the page waiting
for results. Streaming makes the 3–8 second Claude response feel instant — the first
sentence arrives in ~500ms. A plan or report is consumed after it fully loads (users
click a button, then review the whole output). Streaming a plan's JSON tool call provides
no UX benefit and complicates the `tool_use` response parsing substantially.

**tool_use and streaming are mutually exclusive in practice.** Streaming tool_use requires
assembling the delta chunks into a tool_call object incrementally, which adds parsing
complexity for no UX gain on short, structured responses.

**Reporting via SSE is already wired.** The `/api/v1/intelligence/interpret/{experiment_id}`
endpoint uses `StreamingResponse` with `text/event-stream`. Adding streaming to the reporter
would require a new SSE endpoint and significant frontend work for a response that's usually
consumed all at once.

**What it rules out:** The interpreter cannot use tool_use for output validation at generation
time. Instead, validation runs on the assembled text *after* the stream completes.

---

## 3. Why template fallbacks instead of cached responses?

**Decision:** When Claude is unavailable, `fallback_plan`, `fallback_interpretation`, and
`fallback_report` generate template-based responses using the actual result values passed in.
The alternative was to cache a previous successful Claude response and replay it.

**Cached responses are wrong by construction.** A cached plan for Experiment A will have
Experiment A's hypothesis, metric, and MDE. If Experiment B triggers a fallback, the user
would see Experiment A's plan with different numbers — actively misleading. Templates are
parameterized: they receive `stats_result` and `ml_result` from the current experiment,
so every number in the fallback is numerically correct.

**Cache invalidation is hard.** Cached responses must be invalidated when the prompt
version changes, when the experiment is updated, and when the stats results are recomputed.
Templates have no cache to invalidate.

**Fallback clarity matters.** Every template response is prefixed with
`[Auto-generated — AI unavailable]` and the `prompt_version` ends in `_fallback`. Cached
responses are indistinguishable from live AI output unless the metadata is carefully
tracked — a persistent source of confusion for audit.

**What it rules out:** Template fallbacks are less fluent than cached AI output. For the
planner, this is fine (it asks standard questions). For interpretation and reports, the
template language is correct but formulaic. This is an acceptable tradeoff — the fallback
is explicitly labelled and users know AI is unavailable.

---

## 4. Why an in-memory rate limiter instead of Redis?

**Decision:** `RateLimiter` uses a `threading.Lock` and a `defaultdict[str, list[datetime]]`
to implement a sliding-window token bucket. Redis was the obvious alternative.

**Phase 3 is a single-process deployment.** Axiom runs as one Uvicorn worker (or one
Gunicorn worker with async). In a single process, an in-memory lock is atomic with zero
network overhead. Redis adds a network hop, a connection pool, and a hard dependency on
an external service — all for a feature that protects Claude API costs, not user data.

**The rate limiter is not a security boundary.** Its purpose is to prevent accidental
Claude cost explosions from a single session, not to prevent coordinated multi-process
attacks. A sophisticated attacker distributing requests across IPs or sessions is outside
the threat model for this limiter; that case is handled by `slowapi` at the API middleware
layer.

**Redis introduces operational burden.** Running Redis requires Docker configuration, health
checks, connection management, and failure handling. The in-memory implementation has no
dependencies beyond Python's standard library.

**Migration path is clear.** `RateLimiter` is used only through a single interface
(`check(session_id, max_calls, window_seconds) -> RateLimitResult`). Swapping in a Redis
implementation requires changing one class with no API surface changes.

**What it rules out:** In-memory state is lost on process restart and is not shared across
multiple workers. If Axiom scales to multiple Uvicorn workers, the rate limiter must be
replaced with a Redis-backed implementation before deploying to multi-worker production.

---

## 5. Why a grounding validator instead of just trusting Claude?

**Decision:** After each Claude response, the intelligence layer runs explicit grounding checks:
`_validate_grounding()` in the interpreter and `OutputValidator.validate_report()` in the
reporter scan for lift percentage drift, SHIP-when-not-significant, and statistical jargon
in non-technical sections.

**Claude hallucinates numbers under specific conditions.** The interpreter prompt injects
`lift_pct: +15.2000%`. In practice, Claude sometimes rounds, converts, or restates the
number differently — "a 15% lift" when the actual value is 15.2. For a decision tool
used by stakeholders, a percentage that's off by 0.2pp is acceptable; a percentage that's
off by 5pp is a material error. The validator catches the latter.

**SHIP/not-significant is a safety invariant.** If Claude recommends shipping an experiment
that the stats engine flagged as non-significant, that's a categorical error — not a style
issue. `validate_report` auto-corrects `SHIP → EXTEND` in this case and logs at `WARNING`.
Without the validator, this error would propagate silently to the stakeholder report.

**The alternative — pure prompt engineering — is fragile.** "Never recommend shipping if
is_significant=False" in a system prompt works most of the time. Grounding validators work
all the time, because they check the output regardless of what the prompt said. They compose
with prompt improvements rather than replacing them.

**What it rules out:** The validator adds a post-processing step that can (in theory) produce
false positives — e.g., flagging a legitimate mention of "15%" in a discussion of a
different experiment phase. The current implementation mitigates this by only logging
warnings (not blocking), except for the SHIP/significance auto-fix which is a clear rule
with no legitimate exceptions.

---

## 6. Why prompt versioning, and what does it enable?

**Decision:** Every prompt constant in `prompts/` has a version suffix (`planner_v1`,
`interpreter_v1`, `reporter_v1`). The version is stored in `ai_interactions.prompt_version`
alongside every logged Claude call.

**Reproducibility for audit.** When a stakeholder asks "why did Axiom recommend shipping
Experiment 42?", the answer must include what prompt was in effect at the time. Without
prompt versioning, prompt changes are invisible in the audit trail.

**Safe prompt iteration.** Improving a prompt means creating `planner_v2.txt` and a new
`PROMPT_VERSION = "planner_v2"` constant, then updating the caller. The old version remains
in the repo and in the DB. An offline evaluation (`scripts/eval_ai.py`) can compare v1 vs
v2 responses on the same inputs before any production deployment.

**Cost attribution.** Prompt versions differ in length (number of input tokens). Storing
`prompt_version` in `ai_interactions` lets the cost monitoring query break down spend by
prompt version — useful when evaluating whether a longer, more expensive prompt actually
improves output quality.

**A/B testing prompts.** Two prompt versions can be deployed simultaneously with traffic
splitting (e.g., 10% of requests use v2). The `prompt_version` field in `ai_interactions`
makes it trivial to query results by version and compare output quality, cost, and latency.

**What it rules out:** `_V1` constants are not overwritten in place. When v2 is promoted to
production, v1 must be explicitly retired (the constant can remain in the file, unused, for
historical reference). This adds a small amount of file churn but eliminates the risk of
silently changing behavior for live experiments.
