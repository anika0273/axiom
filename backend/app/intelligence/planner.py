"""Experiment planning intelligence layer.

Converts natural-language experiment descriptions into structured, statistically
validated plans. Claude extracts qualitative structure; the stats engine is the
sole source of truth for all numerical sample-size recommendations.

Flow:
  1. Sanitize and validate input (length, injection detection)
  2. Call Claude via tool_use — returns structured plan or clarifying questions
  3. If plan returned: verify sample size with stats engine (mandatory)
  4. Validate plan against Axiom's statistical conventions
  5. Log call to ai_interactions table
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Literal

import anthropic
from pydantic import BaseModel, Field

from app.core.config import settings
from app.intelligence.fallbacks import fallback_plan as _fallback_plan
from app.intelligence.guardrails import (
    ClaudeCallWrapper,
    InputGuardrail,
    OutputValidator,
)
from app.models.experiment import AIInteraction, InteractionType
from app.stats.power import SampleSizeResult, calculate_sample_size, runtime_estimate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROMPT_VERSION = "planner_v1"
MAX_INPUT_CHARS = 2000
TIMEOUT_SECONDS = 25.0
CLAUDE_MODEL = "claude-sonnet-4-6"
_output_validator = OutputValidator()

_COST_PER_INPUT_TOKEN = 3.0 / 1_000_000
_COST_PER_OUTPUT_TOKEN = 15.0 / 1_000_000
_SAMPLE_SIZE_DISCREPANCY_THRESHOLD = 0.15

_SYSTEM_PROMPT: str = (Path(__file__).parent / "prompts" / "planner_v1.txt").read_text(
    encoding="utf-8"
)


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class PrimaryMetric(BaseModel):
    """The primary optimisation metric for an experiment."""

    name: str
    type: Literal["proportion", "mean", "ratio"]
    baseline: float | None = None


class StatisticalConfig(BaseModel):
    """Statistical test configuration."""

    alpha: float = 0.05
    power: float = 0.80
    test_type: str = "two_proportion"
    sequential_testing: bool = False
    cuped_applicable: bool = False


class ExperimentPlan(BaseModel):
    """A fully structured A/B experiment plan."""

    experiment_name: str
    hypothesis: str
    primary_metric: PrimaryMetric
    recommended_mde: float | None = None
    sample_size_per_group: int | None = None
    estimated_runtime_days: float | None = None
    secondary_metrics: list[str] = Field(default_factory=list)
    guardrail_metrics: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    statistical_config: StatisticalConfig = Field(default_factory=StatisticalConfig)
    clarifying_questions: list[str] = Field(default_factory=list)
    planner_notes: str = ""


class ExperimentPlanResult(BaseModel):
    """Top-level result returned by plan_experiment."""

    plan: ExperimentPlan | None = None
    needs_clarification: bool = False
    clarifying_questions: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]
    confidence_reasoning: str
    stats_engine_verification: SampleSizeResult | None = None
    prompt_version: str = PROMPT_VERSION


class ValidationResult(BaseModel):
    """Output of validate_plan."""

    valid: bool
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Claude tool schema
# ---------------------------------------------------------------------------

_TOOL_SCHEMA: dict[str, Any] = {
    "name": "create_experiment_plan",
    "description": (
        "Output a structured A/B experiment plan from a natural-language description. "
        "ALWAYS call this tool — never respond in plain text. "
        "When the description is too vague to plan reliably, set needs_clarification=true "
        "and populate clarifying_questions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "experiment_name": {
                "type": "string",
                "description": "Short, descriptive experiment name.",
            },
            "hypothesis": {
                "type": "string",
                "description": "One-sentence scientific hypothesis.",
            },
            "primary_metric": {
                "type": "object",
                "description": "Primary metric to optimise.",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "snake_case metric name, e.g. checkout_conversion_rate.",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["proportion", "mean", "ratio"],
                    },
                    "baseline": {
                        "type": ["number", "null"],
                        "description": (
                            "Current baseline value as a decimal (e.g. 0.03 for 3%). "
                            "Set null if not stated in the description — never estimate it."
                        ),
                    },
                },
                "required": ["name", "type", "baseline"],
            },
            "recommended_mde": {
                "type": ["number", "null"],
                "description": (
                    "Minimum detectable effect as an absolute value (e.g. 0.005 for 0.5pp). "
                    "Only set for proportion metrics when a target improvement is stated or "
                    "clearly inferable. Never invent a number."
                ),
            },
            "daily_traffic_estimate": {
                "type": ["integer", "null"],
                "description": (
                    "Daily eligible subjects extracted from the description "
                    "(e.g. 500 from 'we get 500 orders per day'). Null if not stated."
                ),
            },
            "secondary_metrics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Secondary metric names to track alongside the primary.",
            },
            "guardrail_metrics": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Guardrail metric names to protect against side effects. "
                    "Always include at least one."
                ),
            },
            "risks": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Concrete, experiment-specific risks and caveats. "
                    "At least 2 required. Be specific — not generic."
                ),
            },
            "statistical_config": {
                "type": "object",
                "properties": {
                    "alpha": {"type": "number"},
                    "power": {"type": "number"},
                    "test_type": {"type": "string"},
                    "sequential_testing": {"type": "boolean"},
                    "cuped_applicable": {"type": "boolean"},
                },
                "required": [
                    "alpha",
                    "power",
                    "test_type",
                    "sequential_testing",
                    "cuped_applicable",
                ],
            },
            "needs_clarification": {
                "type": "boolean",
                "description": (
                    "Set true when baseline rate is missing, metric type is ambiguous, "
                    "or the description is too vague to produce a reliable plan."
                ),
            },
            "clarifying_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific questions to ask when needs_clarification is true.",
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": (
                    "high: baseline + traffic provided, metric unambiguous. "
                    "medium: minor inference required. "
                    "low: key numbers missing or metric ambiguous."
                ),
            },
            "confidence_reasoning": {
                "type": "string",
                "description": "One sentence explaining the confidence level.",
            },
        },
        "required": [
            "experiment_name",
            "hypothesis",
            "primary_metric",
            "needs_clarification",
            "confidence",
            "confidence_reasoning",
        ],
    },
}


# ---------------------------------------------------------------------------
# Input sanitization (now delegated to InputGuardrail)
# ---------------------------------------------------------------------------


def _sanitize_input(description: str) -> tuple[str, str | None]:
    """Delegate to InputGuardrail.sanitize for uniform guardrail logic.

    Returns:
        (cleaned_text, error_message_or_None)
    """
    result = InputGuardrail.sanitize(description, max_chars=MAX_INPUT_CHARS)
    return result.text, result.rejection_reason


# ---------------------------------------------------------------------------
# Stats engine integration
# ---------------------------------------------------------------------------


def _run_stats_verification(
    tool_input: dict[str, Any],
    daily_traffic: int | None,
) -> tuple[int | None, float | None, SampleSizeResult | None, str]:
    """Call the stats engine to compute verified sample size and runtime.

    Claude never provides sample sizes; this function is the sole source of
    truth for all numerical planning outputs.

    Args:
        tool_input: Raw dict from Claude's tool_use block.
        daily_traffic: Daily eligible subjects (from context or tool extraction).

    Returns:
        (sample_size_per_group, estimated_runtime_days, SampleSizeResult, note)
    """
    primary = tool_input.get("primary_metric") or {}
    baseline = primary.get("baseline")
    mde = tool_input.get("recommended_mde")
    stat_cfg = tool_input.get("statistical_config") or {}
    alpha = float(stat_cfg.get("alpha", 0.05))
    power = float(stat_cfg.get("power", 0.80))

    # Use daily_traffic from context, or from what Claude extracted from the description
    extracted_traffic = tool_input.get("daily_traffic_estimate")
    effective_traffic = daily_traffic or extracted_traffic

    if baseline is None or mde is None:
        return (
            None,
            None,
            None,
            "Sample size not computed — baseline rate or MDE not available in description.",
        )

    try:
        stats_result = calculate_sample_size(
            baseline_rate=float(baseline),
            mde=float(mde),
            alpha=alpha,
            power=power,
        )
    except ValueError as exc:
        logger.warning("stats engine error: %s", exc)
        return None, None, None, f"Stats engine error: {exc}"

    # Check for discrepancy if the context somehow provided a competing value
    # (defensive — Claude's schema does not include sample_size_per_group)
    note = "Sample size verified by stats engine."

    runtime_days: float | None = None
    if effective_traffic and effective_traffic > 0:
        try:
            rt = runtime_estimate(
                required_sample_size=stats_result.total_sample_size,
                daily_traffic=int(effective_traffic),
            )
            runtime_days = rt.days_expected
        except ValueError as exc:
            logger.warning("runtime estimate error: %s", exc)

    return stats_result.control_size, runtime_days, stats_result, note


# ---------------------------------------------------------------------------
# DB logging
# ---------------------------------------------------------------------------


async def _log_to_db(
    db: Any,
    *,
    description: str,
    tool_output_json: str,
    input_tokens: int,
    output_tokens: int,
    confidence: str,
    duration_ms: int,
) -> None:
    """Write a row to ai_interactions. Fails silently so planning is never blocked."""
    if db is None:
        return
    try:
        cost = (
            input_tokens * _COST_PER_INPUT_TOKEN
            + output_tokens * _COST_PER_OUTPUT_TOKEN
        )
        record = AIInteraction(
            experiment_id=None,
            interaction_type=InteractionType.plan,
            user_prompt=description,
            ai_response=tool_output_json,
            tokens_used=input_tokens + output_tokens,
            prompt_version=PROMPT_VERSION,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
            confidence=confidence,
            duration_ms=duration_ms,
        )
        db.add(record)
        await db.flush()
    except Exception as exc:
        logger.warning("Failed to log AI interaction to DB: %s", exc)


# ---------------------------------------------------------------------------
# Core planning function
# ---------------------------------------------------------------------------


async def plan_experiment(
    description: str,
    context: dict[str, Any] | None = None,
    db: Any = None,
) -> ExperimentPlanResult:
    """Convert a natural-language experiment description into a structured plan.

    Claude extracts qualitative structure and raises clarifying questions when
    information is insufficient. All sample sizes are computed by the stats
    engine — Claude never produces these values.

    Args:
        description: Free-text description of the experiment.
        context: Optional dict with extra context, e.g. {'daily_traffic': 500}.
        db: AsyncSession for logging. May be None in tests.

    Returns:
        ExperimentPlanResult — either a full plan or a list of clarifying questions.

    Raises:
        ValueError: Input exceeds MAX_INPUT_CHARS.
        PermissionError: Prompt injection pattern detected.
        TimeoutError: Claude API timed out.
        RuntimeError: Claude API returned an unexpected response.
    """
    cleaned, err = _sanitize_input(description)
    if err:
        if "character limit" in err:
            raise ValueError(err)
        raise PermissionError(err)

    ctx = context or {}
    user_message = cleaned
    if ctx:
        user_message = f"{cleaned}\n\nAdditional context:\n{json.dumps(ctx, indent=2)}"

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    t0 = time.monotonic()
    wrapper = ClaudeCallWrapper()

    async def _call_claude() -> Any:
        return await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            tools=[_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "create_experiment_plan"},
            messages=[{"role": "user", "content": user_message}],
            timeout=TIMEOUT_SECONDS,
        )

    response, used_fallback = await wrapper.call_with_retry(
        _call_claude,
        max_retries=2,
        retry_delay=2.0,
        timeout=TIMEOUT_SECONDS,
    )

    if used_fallback or response is None:
        # Claude is unavailable — return a safe fallback asking for clarification
        fb = _fallback_plan(cleaned)
        return ExperimentPlanResult(
            plan=None,
            needs_clarification=True,
            clarifying_questions=fb["clarifying_questions"],
            confidence="low",
            confidence_reasoning=fb["confidence_reasoning"],
            stats_engine_verification=None,
            prompt_version=PROMPT_VERSION,
        )

    duration_ms = int((time.monotonic() - t0) * 1000)
    input_tokens: int = response.usage.input_tokens
    output_tokens: int = response.usage.output_tokens

    tool_block = next(
        (b for b in response.content if b.type == "tool_use"),
        None,
    )
    if tool_block is None:
        fb = _fallback_plan(cleaned)
        return ExperimentPlanResult(
            plan=None,
            needs_clarification=True,
            clarifying_questions=fb["clarifying_questions"],
            confidence="low",
            confidence_reasoning=fb["confidence_reasoning"],
            stats_engine_verification=None,
            prompt_version=PROMPT_VERSION,
        )

    tool_input: dict[str, Any] = tool_block.input
    needs_clarification = bool(tool_input.get("needs_clarification", False))
    clarifying_questions: list[str] = tool_input.get("clarifying_questions") or []
    confidence: Literal["high", "medium", "low"] = tool_input.get("confidence", "low")
    confidence_reasoning: str = tool_input.get("confidence_reasoning", "")

    await _log_to_db(
        db,
        description=cleaned,
        tool_output_json=json.dumps(tool_input),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        confidence=confidence,
        duration_ms=duration_ms,
    )

    if needs_clarification:
        return ExperimentPlanResult(
            plan=None,
            needs_clarification=True,
            clarifying_questions=clarifying_questions,
            confidence=confidence,
            confidence_reasoning=confidence_reasoning,
            stats_engine_verification=None,
            prompt_version=PROMPT_VERSION,
        )

    # Build typed plan from Claude's tool output
    primary_raw = tool_input.get("primary_metric") or {}
    primary_metric = PrimaryMetric(
        name=primary_raw.get("name", ""),
        type=primary_raw.get("type", "proportion"),
        baseline=primary_raw.get("baseline"),
    )

    stat_cfg_raw = tool_input.get("statistical_config") or {}
    statistical_config = StatisticalConfig(
        alpha=float(stat_cfg_raw.get("alpha", 0.05)),
        power=float(stat_cfg_raw.get("power", 0.80)),
        test_type=stat_cfg_raw.get("test_type", "two_proportion"),
        sequential_testing=bool(stat_cfg_raw.get("sequential_testing", False)),
        cuped_applicable=bool(stat_cfg_raw.get("cuped_applicable", False)),
    )

    # Stats engine verification — mandatory, never skipped
    daily_traffic = ctx.get("daily_traffic")
    sample_size, runtime_days, stats_result, note = _run_stats_verification(
        tool_input, daily_traffic=daily_traffic
    )

    # Output validation — log issues, require fallback only on blocking errors
    stats_dict: dict[str, Any] = {}
    if stats_result is not None:
        stats_dict["sample_size_per_group"] = stats_result.control_size
    validation_report = _output_validator.validate_plan(tool_input, stats_dict)
    if validation_report.issues:
        logger.warning(
            "planner validate_plan found %d issue(s) for experiment=%r: %s",
            len(validation_report.issues),
            tool_input.get("experiment_name", ""),
            [i.message for i in validation_report.issues],
        )
    if validation_report.requires_fallback:
        fb = _fallback_plan(cleaned)
        return ExperimentPlanResult(
            plan=None,
            needs_clarification=True,
            clarifying_questions=fb["clarifying_questions"],
            confidence="low",
            confidence_reasoning=f"Plan validation failed: {fb['confidence_reasoning']}",
            stats_engine_verification=None,
            prompt_version=PROMPT_VERSION,
        )

    plan = ExperimentPlan(
        experiment_name=tool_input.get("experiment_name", ""),
        hypothesis=tool_input.get("hypothesis", ""),
        primary_metric=primary_metric,
        recommended_mde=tool_input.get("recommended_mde"),
        sample_size_per_group=sample_size,
        estimated_runtime_days=runtime_days,
        secondary_metrics=list(tool_input.get("secondary_metrics") or []),
        guardrail_metrics=list(tool_input.get("guardrail_metrics") or []),
        risks=list(tool_input.get("risks") or []),
        statistical_config=statistical_config,
        clarifying_questions=[],
        planner_notes=note,
    )

    # Validate and downgrade confidence if plan has structural problems
    validation = validate_plan(plan)
    if not validation.valid and confidence == "high":
        confidence = "medium"
        confidence_reasoning += f" (downgraded: {'; '.join(validation.errors)})"

    return ExperimentPlanResult(
        plan=plan,
        needs_clarification=False,
        clarifying_questions=[],
        confidence=confidence,
        confidence_reasoning=confidence_reasoning,
        stats_engine_verification=stats_result,
        prompt_version=PROMPT_VERSION,
    )


# ---------------------------------------------------------------------------
# Plan validation
# ---------------------------------------------------------------------------


def validate_plan(plan: ExperimentPlan) -> ValidationResult:
    """Validate a plan against Axiom's statistical conventions.

    Args:
        plan: The structured plan to validate.

    Returns:
        ValidationResult with any errors (blocking) and warnings (advisory).
    """
    errors: list[str] = []
    warnings: list[str] = []

    primary = plan.primary_metric

    if primary.baseline is not None:
        if not (0.001 <= primary.baseline <= 0.999):
            errors.append(
                f"baseline {primary.baseline} is outside valid range (0.001, 0.999)."
            )
        if primary.type == "proportion" and primary.baseline > 1.0:
            errors.append(f"baseline={primary.baseline} > 1.0 for a proportion metric.")

    if plan.recommended_mde is not None:
        if not (0.001 <= abs(plan.recommended_mde) <= 0.5):
            warnings.append(
                f"recommended_mde={plan.recommended_mde} is outside the typical "
                "range (0.001 – 0.5). Verify this is intentional."
            )

    if plan.estimated_runtime_days is not None:
        if not (3.0 <= plan.estimated_runtime_days <= 365.0):
            warnings.append(
                f"estimated_runtime_days={plan.estimated_runtime_days:.1f} is "
                "outside the typical range (3 – 365 days)."
            )

    alpha = plan.statistical_config.alpha
    if alpha not in (0.01, 0.05, 0.10):
        warnings.append(
            f"alpha={alpha} is non-standard. Axiom defaults are 0.01, 0.05, or 0.10."
        )

    guardrail_set = set(plan.guardrail_metrics)
    if primary.name in guardrail_set:
        errors.append(
            f"Primary metric '{primary.name}' must not appear in guardrail_metrics."
        )

    return ValidationResult(valid=len(errors) == 0, warnings=warnings, errors=errors)


# ---------------------------------------------------------------------------
# Standalone clarifying-questions extractor
# ---------------------------------------------------------------------------


async def extract_clarifying_questions(description: str) -> list[str]:
    """Return clarifying questions needed before planning can proceed.

    Useful as a lightweight fallback when plan_experiment returns
    needs_clarification=True, or as a timeout fallback in the API layer.

    Args:
        description: The vague or incomplete experiment description.

    Returns:
        List of specific clarifying questions, or a generic prompt if the
        API call itself fails.
    """
    cleaned, err = _sanitize_input(description)
    if err:
        return [
            "Please provide a valid experiment description (under 2000 characters, no system instructions)."
        ]

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    try:
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            tools=[_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "create_experiment_plan"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        "This experiment description is incomplete. "
                        "Generate the clarifying questions needed before planning can start:\n\n"
                        f"{cleaned}"
                    ),
                }
            ],
            timeout=TIMEOUT_SECONDS,
        )
    except (anthropic.APIError, TimeoutError) as exc:
        logger.warning("extract_clarifying_questions failed: %s", exc)
        return [
            "What is the primary metric you want to improve?",
            "What is the current baseline conversion rate for that metric?",
            "How many eligible users or sessions do you see per day?",
            "What minimum improvement would make this experiment worth running?",
        ]

    tool_block = next(
        (b for b in response.content if b.type == "tool_use"),
        None,
    )
    if tool_block is None:
        return []

    return list(tool_block.input.get("clarifying_questions") or [])
