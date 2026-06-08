import { useState } from "react"

// ── status colours ────────────────────────────────────────────────────────────

const STATUS_COLOR = {
  PASS: "var(--color-accent-green)",
  WARN: "var(--color-accent-amber)",
  FAIL: "var(--color-accent-red)",
  SKIPPED: "var(--color-text-muted)",
  INFO: "var(--color-text-muted)",
  SHIP: "var(--color-accent-green)",
  CAUTION: "var(--color-accent-amber)",
  "KEEP RUNNING": "var(--color-accent-amber)",
  "NO EFFECT": "var(--color-text-muted)",
  INVALID: "var(--color-accent-red)",
}

function actColor(status) {
  return STATUS_COLOR[status] ?? "var(--color-text-muted)"
}

function badgeBg(color) {
  if (color === "var(--color-accent-green)") return "rgba(16,185,129,0.15)"
  if (color === "var(--color-accent-amber)") return "rgba(245,158,11,0.15)"
  if (color === "var(--color-accent-red)")   return "rgba(239,68,68,0.15)"
  return "rgba(71,85,105,0.15)"
}

// ── Act card ──────────────────────────────────────────────────────────────────

function Act({ step, title, status, statusLabel, story, detail }) {
  const [open, setOpen] = useState(false)
  const color = actColor(status)

  return (
    <div
      style={{
        background: "var(--color-bg-card)",
        border: "1px solid var(--color-border-subtle)",
        borderLeft: `3px solid ${color}`,
        borderRadius: 8,
        padding: "16px 20px",
      }}
    >
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        <span
          style={{
            fontFamily: "DM Mono, monospace",
            fontSize: 11,
            color: "var(--color-text-muted)",
            flexShrink: 0,
          }}
        >
          {step}
        </span>
        <span
          style={{
            fontSize: 14,
            fontWeight: 500,
            color: "var(--color-text-primary)",
            flexGrow: 1,
          }}
        >
          {title}
        </span>
        <span
          style={{
            fontFamily: "DM Mono, monospace",
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: color,
            background: badgeBg(color),
            borderRadius: 4,
            padding: "2px 8px",
            flexShrink: 0,
          }}
        >
          {statusLabel ?? status}
        </span>
      </div>

      {/* Story — string or ReactNode */}
      <div
        style={{
          fontSize: 13,
          color: "var(--color-text-secondary)",
          lineHeight: 1.7,
          marginBottom: 10,
        }}
      >
        {typeof story === "string" ? (
          <p style={{ margin: 0 }}>{story}</p>
        ) : (
          story
        )}
      </div>

      {/* Technical detail toggle */}
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          background: "none",
          border: "none",
          padding: 0,
          cursor: "pointer",
          fontSize: 11,
          color: "var(--color-text-muted)",
          display: "flex",
          alignItems: "center",
          gap: 4,
        }}
      >
        Technical detail {open ? "▲" : "▾"}
      </button>

      {open && (
        <div
          style={{
            background: "var(--color-bg-elevated)",
            borderRadius: 6,
            padding: "10px 14px",
            marginTop: 10,
            fontFamily: "DM Mono, monospace",
            fontSize: 11,
            color: "var(--color-text-secondary)",
            lineHeight: 1.6,
            whiteSpace: "pre-wrap",
          }}
        >
          {detail}
        </div>
      )}
    </div>
  )
}

// ── act builders ──────────────────────────────────────────────────────────────

function buildAct1(result) {
  const { anomaly } = result

  if (anomaly == null) {
    return {
      status: "SKIPPED",
      statusLabel: "SKIPPED",
      story:
        "Before looking at results, we normally check for Sample Ratio Mismatch — whether users were split evenly between groups. This check requires daily time-series data, which was not provided for this experiment. The randomization check was skipped.",
      detail: "No anomaly data available.",
    }
  }

  const checks = anomaly.checks ?? []
  const srmFailed = checks.some(
    (c) =>
      !c.passed &&
      (c.name?.toLowerCase().includes("srm") ||
        c.name?.toLowerCase().includes("sample_ratio")),
  )

  const detailLines = checks.length
    ? checks.map(
        (c) =>
          `${c.passed ? "✓" : "✗"} ${c.name ?? "check"} — ${
            c.passed ? "passed" : "FAILED"
          }${c.score != null ? ` — score: ${Number(c.score).toFixed(3)}` : ""}${
            c.severity ? ` — severity: ${c.severity}` : ""
          }`,
      )
    : ["No checks data."]

  if (srmFailed) {
    return {
      status: "FAIL",
      statusLabel: "FAIL",
      story:
        "Before looking at any results, we check whether the experiment ran correctly. A critical problem was detected: Sample Ratio Mismatch (SRM). We expected an even split between groups but observed a suspicious imbalance. This means the randomization may be broken — the control and treatment groups might not be comparable. The results below cannot be fully trusted until this is investigated.",
      detail: detailLines.join("\n"),
    }
  }

  return {
    status: "PASS",
    statusLabel: "PASS",
    story:
      "Before looking at any results, we check whether the experiment itself ran correctly. The most important check is called Sample Ratio Mismatch (SRM) — it verifies that users were split evenly between control and treatment. If this is broken, the groups are not comparable and no result can be trusted. All checks passed. The randomization looks clean.",
    detail: detailLines.join("\n"),
  }
}

function buildAct2(result) {
  const {
    isSignificant,
    warnings = [],
    expType,
    controlRate,
    treatmentRate,
    pValue,
    liftPct,
    liftAbs,
    ciLow,
    ciHigh,
    plainEnglish,
  } = result

  const isProportion = expType === "proportion"
  const testName = isProportion
    ? "z-test (for conversion rates)"
    : "t-test (for averages)"

  const controlFmt = isProportion
    ? `${(controlRate * 100).toFixed(2)}%`
    : (controlRate?.toFixed(2) ?? "?")

  const treatmentFmt = isProportion
    ? `${(treatmentRate * 100).toFixed(2)}%`
    : (treatmentRate?.toFixed(2) ?? "?")

  const liftAbsFmt = isProportion
    ? `${(liftAbs * 100).toFixed(2)} percentage points`
    : `${liftAbs?.toFixed(2) ?? "?"} units`

  const ciUnit = isProportion ? "%" : ""
  const ciLowFmt  = ciLow  != null ? `${ciLow.toFixed(2)}${ciUnit}`  : "?"
  const ciHighFmt = ciHigh != null ? `${ciHigh.toFixed(2)}${ciUnit}` : "?"
  const pValueFmt = pValue != null ? pValue.toFixed(4) : "?"
  const liftPctFmt = liftPct?.toFixed(1) ?? "?"

  const isUnderpowered = warnings.some((w) => {
    const text = typeof w === "string" ? w : (w?.message ?? w?.text ?? "")
    return (
      text.toLowerCase().includes("underpowered") ||
      text.toLowerCase().includes("under-powered")
    )
  })

  let status, statusLabel, story

  if (isSignificant) {
    status = "PASS"
    statusLabel = "SIGNIFICANT"
    story =
      `We ran a ${testName} comparing the two groups. ` +
      `The control group measured ${controlFmt} and the treatment group measured ${treatmentFmt} — ` +
      `a difference of ${liftAbsFmt} (${liftPctFmt}% relative lift). ` +
      `The p-value (p=${pValueFmt}) is below the 5% threshold, which means there is less than a 5% chance this difference is random noise. ` +
      `The 95% confidence interval (${ciLowFmt} to ${ciHighFmt}) tells us the true effect is most likely somewhere in that range. ` +
      `This result is statistically significant.`
  } else {
    status = isUnderpowered ? "WARN" : "INFO"
    statusLabel = isUnderpowered ? "UNDERPOWERED" : "NOT YET SIGNIFICANT"
    story =
      `We ran a ${testName} comparing the two groups. ` +
      `The control group measured ${controlFmt} and the treatment group measured ${treatmentFmt} — ` +
      `an observed difference of ${liftAbsFmt} (${liftPctFmt}% relative lift). ` +
      `However, the p-value (p=${pValueFmt}) is above the 5% threshold. ` +
      `This means the observed difference could plausibly be random variation — we do not have enough evidence yet to call this real.` +
      (plainEnglish ? " " + plainEnglish : "")
  }

  const detail = [
    `test type: ${testName}`,
    `p-value: ${pValueFmt}`,
    `confidence interval: ${ciLowFmt} to ${ciHighFmt}`,
    `lift (absolute): ${liftAbsFmt}`,
    `lift (relative): ${liftPctFmt}%`,
    `alpha threshold: 5% (0.05)`,
  ].join("\n")

  return { status, statusLabel, story, detail }
}

function buildAct3(result) {
  const { hte, segments, liftPct } = result

  if (!hte) {
    return {
      status: "SKIPPED",
      statusLabel: "SKIPPED",
      story:
        "The ML analysis requires user-level feature data alongside outcomes. No feature columns were found in the uploaded data, so heterogeneous treatment effect (HTE) analysis was skipped. To enable this, include optional feature columns when uploading your CSV.",
      detail: "No HTE data available.",
    }
  }

  const stability = hte.stability_score ?? 0
  const status = stability >= 0.8 ? "PASS" : "WARN"
  const statusLabel = stability >= 0.8 ? "STRONG SIGNAL" : "WEAK SIGNAL"

  const rawFeature = hte.top_interactions?.[0] ?? "f0"
  const featureName = rawFeature
    .replace(/_x_treat$/, "")
    .replace(/_/g, " ")
    .trim()
  const isCriteoFeature = /^f\d+$/.test(featureName)
  const featureLabel = isCriteoFeature
    ? `Feature ${featureName.replace("f", "")} from the Criteo dataset (${featureName})`
    : featureName

  const ateFmt       = hte.ate != null ? Number(hte.ate).toFixed(4) : "?"
  const stabilityFmt = stability.toFixed(2)

  let stabilityComment
  if (stability >= 0.9) {
    stabilityComment =
      "a very high score that means this finding is robust, not noise"
  } else if (stability >= 0.7) {
    stabilityComment =
      "a reasonable score suggesting the signal is real but worth validating with more data"
  } else {
    stabilityComment = "a low score suggesting this finding may not be reliable"
  }

  const topSegment = segments?.segments?.find((s) =>
    segments.responsive_segments?.includes(s.id),
  )
  const topSegmentLift = topSegment?.lift

  const p1 =
    `This treatment does not affect all users equally. ` +
    `The ML analysis found that ${featureLabel} is the strongest signal for who responds to this change. ` +
    `The average treatment effect (ATE=${ateFmt}) is the mean across all users — but that average hides important variation.`

  const p2 =
    `The model was refit three independent times with different random seeds. ` +
    `It found the same pattern each time, giving a stability score (stability=${stabilityFmt}/1.0) — ${stabilityComment}.` +
    (topSegmentLift != null
      ? ` The most responsive user segment shows a lift of ${topSegmentLift.toFixed(2)} — compared to the overall average of ${liftPct?.toFixed(1) ?? "?"}%.`
      : "")

  const story = (
    <>
      <p style={{ margin: "0 0 8px 0" }}>{p1}</p>
      <p style={{ margin: 0 }}>{p2}</p>
    </>
  )

  const detail = [
    "model type: T-learner XGBoost",
    `ATE: ${ateFmt}`,
    `stability score: ${stabilityFmt}/1.0`,
    `top interactions: ${hte.top_interactions?.join(", ") ?? "none"}`,
    hte.ite_threshold != null ? `ITE threshold: ${hte.ite_threshold}` : null,
    hte.n_subjects    != null ? `n subjects: ${hte.n_subjects}`         : null,
  ]
    .filter(Boolean)
    .join("\n")

  return { status, statusLabel, story, detail }
}

function buildAct4(result) {
  const { novelty } = result

  if (!novelty) {
    return {
      status: "SKIPPED",
      statusLabel: "SKIPPED",
      story:
        "Novelty detection requires daily time-series data showing how the treatment effect changes day by day. This data was not provided, so the check was skipped. If you upload daily aggregate data alongside subject rows, Axiom can automatically check whether effects are holding steady or fading.",
      detail: "No novelty data available.",
    }
  }

  const detailLines = [
    `pattern: ${novelty.pattern}`,
    novelty.slope        != null ? `slope: ${novelty.slope}` : null,
    novelty.recommendation       ? `recommendation: ${novelty.recommendation}` : null,
  ]
    .filter(Boolean)
    .join("\n")

  if (novelty.pattern === "NOVELTY") {
    return {
      status: "WARN",
      statusLabel: "NOVELTY EFFECT DETECTED",
      story:
        "A novelty effect was detected. This means the treatment showed a stronger response early on that is now fading. A common cause is that users react positively to something new but lose interest over time. Shipping based on early results would overestimate the long-term impact." +
        (novelty.recommendation ? " " + novelty.recommendation : ""),
      detail: detailLines,
    }
  }

  return {
    status: "PASS",
    statusLabel: "STABLE",
    story:
      "The treatment effect appears stable over time — no significant decay was detected. The lift observed in early days has held through the experiment window, which increases confidence that this is a genuine sustained effect rather than early excitement.",
    detail: detailLines,
  }
}

function buildAct5(result) {
  const {
    isSignificant,
    canTrust,
    novelty,
    pValue,
    liftPct,
    warnings = [],
    hte,
    recommendation,
  } = result

  const pValueFmt  = pValue  != null ? pValue.toFixed(4)  : "?"
  const liftPctFmt = liftPct != null ? liftPct.toFixed(1) : "?"
  const hasNovelty = novelty?.pattern === "NOVELTY"

  const isUnderpowered = warnings.some((w) => {
    const text = typeof w === "string" ? w : (w?.message ?? w?.text ?? "")
    return text.toLowerCase().includes("underpowered")
  })

  let status, statusLabel, openingSentence

  if (!canTrust) {
    status = "INVALID"
    statusLabel = "INVALID"
    openingSentence =
      "The experiment data could not be trusted. A critical data quality issue was detected that prevents reliable conclusions."
  } else if (isSignificant && !hasNovelty) {
    status = "SHIP"
    statusLabel = "SHIP"
    openingSentence =
      "The experiment produced a clear, reliable result. The evidence is strong enough to act on."
  } else if (isSignificant && hasNovelty) {
    status = "CAUTION"
    statusLabel = "CAUTION"
    openingSentence =
      "The experiment is significant, but a novelty effect was detected. Proceed with caution — the long-term impact may be lower than what the data currently shows."
  } else if (isUnderpowered) {
    status = "KEEP RUNNING"
    statusLabel = "KEEP RUNNING"
    openingSentence =
      "The experiment has not yet reached statistical significance, and the sample size suggests it may be underpowered. Collect more data before making a decision."
  } else {
    status = "NO EFFECT"
    statusLabel = "NO EFFECT"
    openingSentence =
      "The experiment did not produce a statistically significant result. There is not enough evidence to conclude that the treatment has a real effect."
  }

  // Randomization summary from Act 1
  const srmFailed = result.anomaly?.checks?.some(
    (c) =>
      !c.passed &&
      (c.name?.toLowerCase().includes("srm") ||
        c.name?.toLowerCase().includes("sample_ratio")),
  )
  const randomizationSummary = result.anomaly
    ? srmFailed
      ? "had critical issues (SRM detected)"
      : "passed all checks"
    : "was not checked (no time-series data provided)"

  // HTE feature label for summary
  let hteSummary = null
  const rawFeature = hte?.top_interactions?.[0]
  if (hte && rawFeature) {
    const featureName = rawFeature.replace(/_x_treat$/, "").replace(/_/g, " ").trim()
    const isCriteo = /^f\d+$/.test(featureName)
    const featureLabel = isCriteo
      ? `Feature ${featureName.replace("f", "")} from the Criteo dataset (${featureName})`
      : featureName
    hteSummary = `The ML analysis found ${featureLabel} as the strongest treatment modifier.`
  }

  const body =
    `The randomization ${randomizationSummary}. ` +
    `The statistical test ${
      isSignificant
        ? "found a significant result"
        : "did not find a significant result"
    } (p=${pValueFmt}).` +
    (hteSummary ? " " + hteSummary : "") +
    (hasNovelty
      ? " A novelty effect was detected — the result may not sustain."
      : "")

  const story = (
    <>
      <p style={{ margin: "0 0 8px 0" }}>{openingSentence}</p>
      <p style={{ margin: recommendation ? "0 0 8px 0" : 0 }}>{body}</p>
      {recommendation && (
        <p style={{ margin: 0 }}>
          <strong style={{ color: "var(--color-text-primary)", fontWeight: 600 }}>
            Recommendation:
          </strong>{" "}
          {recommendation}
        </p>
      )}
    </>
  )

  const detail = [
    `verdict: ${statusLabel}`,
    `significant: ${isSignificant ? "yes" : "no"}`,
    `p-value: ${pValueFmt}`,
    `lift: ${liftPctFmt}%`,
    `can trust: ${canTrust ? "yes" : "no"}`,
    hasNovelty ? "novelty: detected" : "novelty: none",
    hte
      ? `hte: stability=${result.hte?.stability_score?.toFixed(2) ?? "?"}`
      : "hte: skipped",
  ].join("\n")

  return { status, statusLabel, story, detail }
}

// ── main export ───────────────────────────────────────────────────────────────

export default function AnalysisNarrative({ result, experiment }) {
  if (!result) return null

  const acts = [
    { step: "01", title: "Checking the randomization",      ...buildAct1(result) },
    { step: "02", title: "What the data showed",             ...buildAct2(result) },
    { step: "03", title: "Who does it actually help?",       ...buildAct3(result) },
    { step: "04", title: "Is the effect stable over time?",  ...buildAct4(result) },
    { step: "05", title: "The verdict",                      ...buildAct5(result) },
  ]

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 24 }}>
      {acts.map((act) => (
        <Act key={act.step} {...act} />
      ))}
    </div>
  )
}
