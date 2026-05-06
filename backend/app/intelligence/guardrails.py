"""Production-grade guardrails for the Claude intelligence layer.

InputGuardrail   — sanitize and injection-detect user-supplied text
OutputValidator  — post-generation consistency checks with auto-fix
RateLimiter      — in-memory token-bucket for Claude call throttling
ClaudeCallWrapper — retry + timeout + fallback wrapper for any Claude call
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Shared compiled patterns
# ─────────────────────────────────────────────────────────────────────────────

_INJECTION_PATTERNS: tuple[str, ...] = (
    "ignore previous instructions",
    "ignore all previous",
    "system prompt",
    "you are now",
    "forget everything",
    "act as",
    "jailbreak",
    "dan mode",
)

# Matches \x00-\x08, \x0b (VT), \x0c (FF), \x0e-\x1f — preserves \n (\x0a) and \t (\x09)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# Two or more consecutive spaces
_MULTI_SPACE_RE = re.compile(r" {2,}")

# Statistical jargon forbidden in non-technical sections
_PVALUE_PATTERN = re.compile(
    r"\bp[\s]*[=<>!]+\s*0\.\d+"
    r"|\bp-value\b"
    r"|\bz-statistic\b"
    r"|\bz-score\b"
    r"|\bz-test\b"
    r"|\bt-statistic\b"
    r"|\balpha\s*=\s*0\.\d+"
    r"|\bbeta\s*=\s*0\.\d+"
    r"|\bnull hypothesis\b",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SanitizeResult:
    """Output of InputGuardrail.sanitize.

    Attributes:
        text: Cleaned text ready for use in a prompt.
        was_modified: True when control chars or excess whitespace were stripped.
        rejection_reason: Non-None string means the input must be rejected
                          before reaching Claude; None means it is safe.
        modifications: Human-readable log of every transformation applied.
    """

    text: str
    was_modified: bool
    rejection_reason: str | None
    modifications: list[str] = field(default_factory=list)


@dataclass
class ValidationIssue:
    """A single finding from OutputValidator.

    Attributes:
        severity: "error" for blocking issues; "warning" for advisories.
        code: Machine-readable identifier (e.g. "SHIP_NONSIG").
        message: Human-readable description of the issue.
    """

    severity: str
    code: str
    message: str


@dataclass
class ValidationReport:
    """Aggregate output of any OutputValidator check.

    Attributes:
        passed: True when no issues were found (before or after auto-fix).
        issues: All findings, including those that were auto-fixed.
        auto_fixed: Human-readable log of every in-place correction made.
        requires_fallback: True when one or more errors cannot be auto-fixed.
    """

    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    auto_fixed: list[str] = field(default_factory=list)
    requires_fallback: bool = False


@dataclass
class RateLimitResult:
    """Output of RateLimiter.check.

    Attributes:
        allowed: True when the call is within the rate limit.
        calls_remaining: How many more calls are allowed in this window.
        reset_in_seconds: Seconds until the oldest call in the window expires.
    """

    allowed: bool
    calls_remaining: int
    reset_in_seconds: int


# ─────────────────────────────────────────────────────────────────────────────
# InputGuardrail
# ─────────────────────────────────────────────────────────────────────────────


class InputGuardrail:
    """Sanitize and validate user-supplied text before it reaches Claude.

    All methods are static — no instance state needed.
    """

    @staticmethod
    def sanitize(text: str, max_chars: int = 2000) -> SanitizeResult:
        """Clean and validate user input.

        Checks are applied in order:
        1. Length  — reject if len(text) > max_chars.
        2. Injection patterns — reject if any disallowed phrase is found.
        3. Control characters — strip \\x00-\\x1f except \\n and \\t.
        4. Whitespace — collapse runs of spaces; strip leading/trailing.

        Args:
            text: Raw user-supplied text.
            max_chars: Maximum allowed character count (checked before cleaning).

        Returns:
            SanitizeResult where rejection_reason=None means the text is safe.
        """
        modifications: list[str] = []

        # 1. Length check
        if len(text) > max_chars:
            return SanitizeResult(
                text=text,
                was_modified=False,
                rejection_reason=(
                    f"Input exceeds {max_chars} character limit "
                    f"({len(text)} chars). Please shorten your description."
                ),
            )

        # 2. Injection detection (case-insensitive substring match)
        lower = text.lower()
        for pattern in _INJECTION_PATTERNS:
            if pattern in lower:
                return SanitizeResult(
                    text=text,
                    was_modified=False,
                    rejection_reason=(
                        f"Input contains a disallowed pattern: '{pattern}'. "
                        "Please describe your experiment without instructions "
                        "to the AI system."
                    ),
                )

        # 3. Strip control characters (keep \n=\x0a and \t=\x09)
        cleaned = _CONTROL_CHAR_RE.sub("", text)
        if cleaned != text:
            modifications.append("Stripped non-printable control characters.")

        # 4. Collapse multiple spaces and strip surrounding whitespace
        collapsed = _MULTI_SPACE_RE.sub(" ", cleaned).strip()
        if collapsed != cleaned:
            modifications.append(
                "Collapsed multiple spaces and stripped surrounding whitespace."
            )

        return SanitizeResult(
            text=collapsed,
            was_modified=bool(modifications),
            rejection_reason=None,
            modifications=modifications,
        )


# ─────────────────────────────────────────────────────────────────────────────
# OutputValidator
# ─────────────────────────────────────────────────────────────────────────────


class OutputValidator:
    """Validate Claude outputs for consistency, grounding, and safety.

    Methods operate on raw dicts (tool_input / tool_output) rather than typed
    models so they can run before deserialisation.  validate_report mutates the
    dict in-place to apply auto-fixes.
    """

    _PLAN_REQUIRED: tuple[str, ...] = (
        "experiment_name",
        "hypothesis",
        "primary_metric",
        "confidence",
    )
    _CONFIDENCE_VALUES: frozenset[str] = frozenset({"high", "medium", "low"})

    def validate_plan(self, plan: dict, stats_result: dict) -> ValidationReport:
        """Validate a plan tool_input dict against stats engine results.

        Checks:
        - All required fields are present and non-empty.
        - confidence is a valid enum value.
        - sample_size_per_group within 15 % of stats engine value (when both present).
        - No p-value / z-score jargon in hypothesis or planner_notes.

        Args:
            plan: Raw tool_input dict from Claude's create_experiment_plan call.
            stats_result: Dict with optional sample_size_per_group from the stats engine.

        Returns:
            ValidationReport — requires_fallback=True when blocking errors are found.
        """
        issues: list[ValidationIssue] = []
        auto_fixed: list[str] = []

        # Required fields
        for f in self._PLAN_REQUIRED:
            if not plan.get(f):
                issues.append(ValidationIssue(
                    severity="error",
                    code="MISSING_FIELD",
                    message=f"Required field '{f}' is missing or empty.",
                ))

        # Confidence enum
        confidence = plan.get("confidence")
        if confidence and confidence not in self._CONFIDENCE_VALUES:
            issues.append(ValidationIssue(
                severity="error",
                code="INVALID_CONFIDENCE",
                message=(
                    f"confidence='{confidence}' must be one of "
                    f"{sorted(self._CONFIDENCE_VALUES)}."
                ),
            ))

        # Sample size tolerance (15 %)
        plan_n = plan.get("sample_size_per_group")
        stats_n = stats_result.get("sample_size_per_group")
        if plan_n is not None and stats_n is not None and stats_n > 0:
            pct_diff = abs(plan_n - stats_n) / stats_n
            if pct_diff > 0.15:
                issues.append(ValidationIssue(
                    severity="warning",
                    code="SAMPLE_SIZE_MISMATCH",
                    message=(
                        f"Plan sample_size={plan_n} differs from stats engine "
                        f"value {stats_n} by {pct_diff:.1%} (threshold: 15%)."
                    ),
                ))

        # No statistical jargon in text fields
        for field_key in ("hypothesis", "planner_notes"):
            val = plan.get(field_key, "")
            if val and _PVALUE_PATTERN.search(str(val)):
                issues.append(ValidationIssue(
                    severity="warning",
                    code="PVALUE_IN_TEXT",
                    message=f"Statistical jargon (p-value/z-score) found in '{field_key}'.",
                ))
                break

        has_errors = any(i.severity == "error" for i in issues)
        return ValidationReport(
            passed=len(issues) == 0,
            issues=issues,
            auto_fixed=auto_fixed,
            requires_fallback=has_errors,
        )

    def validate_interpretation(
        self, text: str, stats_result: dict
    ) -> ValidationReport:
        """Validate an assembled streaming interpretation for grounding issues.

        Checks:
        - is_significant=True but text says "not significant".
        - is_significant=False but text says "ship" (without negation context).
        - Stated lift % within 5 pp of actual lift_pct.
        - Word count ≤ 300.

        Args:
            text: Assembled full interpretation text from the Claude stream.
            stats_result: Dict with is_significant (bool) and lift_pct (float) keys.

        Returns:
            ValidationReport — all findings are warnings; requires_fallback=False.
        """
        issues: list[ValidationIssue] = []

        is_significant: bool = bool(stats_result.get("is_significant", False))
        lift_pct: float = float(stats_result.get("lift_pct", 0.0))
        lower = text.lower()

        # Significance contradiction
        if is_significant and "not significant" in lower:
            issues.append(ValidationIssue(
                severity="warning",
                code="SIGNIFICANCE_CONTRADICTION",
                message="Text says 'not significant' but is_significant=True.",
            ))

        # SHIP in a non-significant context
        if not is_significant:
            pos = lower.find("ship")
            while pos != -1:
                ctx = lower[max(0, pos - 10): pos + 15]
                if "not" not in ctx and "do_not" not in ctx and "do not" not in ctx:
                    issues.append(ValidationIssue(
                        severity="warning",
                        code="SHIP_FOR_NONSIG",
                        message="Text recommends 'ship' for a non-significant result.",
                    ))
                    break
                pos = lower.find("ship", pos + 1)

        # Lift accuracy: any % mention deviating > 5 pp from actual
        expected = abs(lift_pct)
        for pct_str in re.findall(r"(\d+\.?\d*)%", text):
            val = float(pct_str)
            if val > 1.0 and abs(val - expected) > 5.0:
                issues.append(ValidationIssue(
                    severity="warning",
                    code="LIFT_MISMATCH",
                    message=(
                        f"Text mentions {val:.1f}% but actual lift_pct is "
                        f"{lift_pct:.4f}% — difference exceeds 5 percentage points."
                    ),
                ))
                break

        # Word count
        word_count = len(text.split())
        if word_count > 300:
            issues.append(ValidationIssue(
                severity="warning",
                code="TOO_LONG",
                message=f"Interpretation is {word_count} words (limit: 300).",
            ))

        return ValidationReport(
            passed=len(issues) == 0,
            issues=issues,
            auto_fixed=[],
            requires_fallback=False,
        )

    def validate_report(self, report: dict, stats_result: dict) -> ValidationReport:
        """Validate a report tool_output dict and auto-fix recommendation errors.

        Mutates report in-place for auto-fixed issues. Logs every fix at WARNING.

        Checks:
        - SHIP when is_significant=False → auto-fix to EXTEND.
        - SHIP when can_trust_results=False → auto-fix to INVESTIGATE.
        - No p-value / z-score jargon in sections 1–7.
        - Word count within an acceptable range (200–1500 words).

        Args:
            report: Raw tool_output dict from Claude's write_experiment_report call.
                    Modified in-place for auto-fixed recommendation mismatches.
            stats_result: Dict with is_significant (bool) and optional
                          can_trust_results (bool) keys.

        Returns:
            ValidationReport reflecting all findings including auto-fixes.
        """
        issues: list[ValidationIssue] = []
        auto_fixed: list[str] = []

        is_significant: bool = bool(stats_result.get("is_significant", False))
        can_trust_results: bool = bool(stats_result.get("can_trust_results", True))
        recommendation: str = report.get("recommendation", "")

        # Auto-fix: SHIP + not significant → EXTEND
        if recommendation == "SHIP" and not is_significant:
            report["recommendation"] = "EXTEND"
            msg = "Auto-fixed: SHIP → EXTEND (is_significant=False)."
            auto_fixed.append(msg)
            issues.append(ValidationIssue(severity="error", code="SHIP_NONSIG", message=msg))
            logger.warning("OutputValidator.validate_report: %s", msg)
            recommendation = "EXTEND"

        # Auto-fix: SHIP + cannot trust results → INVESTIGATE
        if recommendation == "SHIP" and not can_trust_results:
            report["recommendation"] = "INVESTIGATE"
            msg = "Auto-fixed: SHIP → INVESTIGATE (can_trust_results=False)."
            auto_fixed.append(msg)
            issues.append(ValidationIssue(severity="error", code="SHIP_INVALID", message=msg))
            logger.warning("OutputValidator.validate_report: %s", msg)

        # Statistical jargon in sections 1–7
        for i in range(1, 8):
            content = report.get(f"section_{i}", "")
            if content and _PVALUE_PATTERN.search(content):
                issues.append(ValidationIssue(
                    severity="warning",
                    code="PVALUE_IN_SECTION",
                    message=f"Statistical jargon detected in section_{i}.",
                ))

        # Word count
        all_text = " ".join(report.get(f"section_{i}", "") for i in range(1, 8))
        word_count = len(all_text.split())
        if word_count > 0 and not (200 <= word_count <= 1500):
            issues.append(ValidationIssue(
                severity="warning",
                code="WORD_COUNT",
                message=f"Report word count is {word_count} (expected 200–1500).",
            ))

        return ValidationReport(
            passed=len(issues) == 0,
            issues=issues,
            auto_fixed=auto_fixed,
            requires_fallback=False,  # all errors here are auto-fixable
        )


# ─────────────────────────────────────────────────────────────────────────────
# RateLimiter
# ─────────────────────────────────────────────────────────────────────────────


class RateLimiter:
    """In-memory sliding-window token bucket. Thread-safe via threading.Lock.

    Suitable for single-process deployments. For multi-process / distributed
    environments, replace with a Redis-backed implementation.
    """

    def __init__(self) -> None:
        self._calls: defaultdict[str, list[datetime]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(
        self,
        session_id: str,
        max_calls: int = 10,
        window_seconds: int = 60,
    ) -> RateLimitResult:
        """Check whether session_id is within its rate limit.

        Evicts expired timestamps before counting, then records this call if
        the limit allows it. Fully atomic under concurrent access.

        Args:
            session_id: Unique identifier for the caller.
            max_calls: Maximum calls permitted in window_seconds.
            window_seconds: Sliding window duration in seconds.

        Returns:
            RateLimitResult — inspect .allowed before proceeding.
        """
        now = datetime.now(timezone.utc)
        cutoff = now.timestamp() - window_seconds

        with self._lock:
            # Evict calls that have fallen outside the window
            self._calls[session_id] = [
                t for t in self._calls[session_id] if t.timestamp() > cutoff
            ]
            current = len(self._calls[session_id])

            if current >= max_calls:
                oldest = self._calls[session_id][0]
                reset_in = int(window_seconds - (now.timestamp() - oldest.timestamp()))
                return RateLimitResult(
                    allowed=False,
                    calls_remaining=0,
                    reset_in_seconds=max(0, reset_in),
                )

            self._calls[session_id].append(now)
            return RateLimitResult(
                allowed=True,
                calls_remaining=max_calls - current - 1,
                reset_in_seconds=window_seconds,
            )


# ─────────────────────────────────────────────────────────────────────────────
# ClaudeCallWrapper
# ─────────────────────────────────────────────────────────────────────────────


class ClaudeCallWrapper:
    """Retry + timeout + fallback wrapper for async Claude API calls.

    Never raises to the caller when a fallback is provided — always returns
    something usable. Without a fallback, returns (None, True) on total failure
    rather than raising, so callers can decide how to handle it.
    """

    async def call_with_retry(
        self,
        func: Callable[..., Any],
        *args: Any,
        max_retries: int = 2,
        retry_delay: float = 2.0,
        timeout: float = 30.0,
        fallback: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> tuple[Any, bool]:
        """Call func with per-attempt timeout, linear retry, and optional fallback.

        Flow:
        1. Call func(*args, **kwargs) inside asyncio.timeout(timeout).
        2. On exception: log, wait retry_delay, try once more (up to max_retries total).
        3. If all attempts fail and fallback is provided: call fallback() and return
           (fallback_result, True).
        4. If all attempts fail with no fallback: return (None, True).
        5. Never raise to the caller.

        Args:
            func: Async callable to invoke.
            *args: Positional arguments forwarded to func (and fallback, if needed).
            max_retries: Total number of attempts (first + retries).
            retry_delay: Seconds to wait between attempts.
            timeout: Per-attempt timeout in seconds (Python 3.12 asyncio.timeout).
            fallback: Optional sync or async callable invoked after all retries
                      are exhausted. Called with no arguments.
            **kwargs: Keyword arguments forwarded to func.

        Returns:
            (result, used_fallback):
              result       — from func on success, from fallback on failure,
                             or None if both fail.
              used_fallback — True when the fallback was invoked.
        """
        last_exc: BaseException | None = None

        for attempt in range(1, max_retries + 1):
            try:
                async with asyncio.timeout(timeout):
                    result = await func(*args, **kwargs)
                status = "success" if attempt == 1 else "retry_success"
                logger.info(
                    "ClaudeCallWrapper status=%s attempt=%d/%d",
                    status, attempt, max_retries,
                )
                return result, False
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "ClaudeCallWrapper attempt=%d/%d failed: %s: %s",
                    attempt, max_retries, type(exc).__name__, exc,
                )
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)

        # All retries exhausted — try fallback
        if fallback is not None:
            try:
                logger.warning(
                    "ClaudeCallWrapper status=fallback_used after %d attempt(s)",
                    max_retries,
                )
                if asyncio.iscoroutinefunction(fallback):
                    fb_result = await fallback()
                else:
                    fb_result = fallback()
                return fb_result, True
            except Exception as fb_exc:
                logger.error("ClaudeCallWrapper fallback also failed: %s", fb_exc)
                return None, True

        logger.error(
            "ClaudeCallWrapper status=failed no fallback available "
            "last_error=%s: %s",
            type(last_exc).__name__ if last_exc else "unknown",
            last_exc,
        )
        return None, True
