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

// ── Techniques checklist ───────────────────────────────────────────────────────

function TechniquesChecklist({ techniques }) {
  const [open, setOpen] = useState(false)
  if (!techniques) return null
  return (
    <div style={{ marginTop: 12 }}>
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
        What we checked {open ? "▲" : "▾"}
      </button>
      {open && (
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 3 }}>
          {techniques.ran?.map((t) => (
            <p key={t} style={{ margin: 0, fontSize: 12, color: "var(--color-text-secondary)" }}>
              <span style={{ color: "var(--color-accent-green)", marginRight: 6 }}>✓</span>
              {t}
            </p>
          ))}
          {techniques.skipped?.map((t) => (
            <p key={t.name} style={{ margin: 0, fontSize: 12, color: "var(--color-text-muted)" }}>
              <span style={{ marginRight: 6 }}>✗</span>
              {t.name} — {t.reason}
            </p>
          ))}
        </div>
      )}
    </div>
  )
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

function buildAct1(result, techniques) {
  const { anomaly } = result

  const anomalyRan = techniques?.ran?.some(
    (t) => t.toLowerCase().includes("anomaly") || t.toLowerCase().includes("sequential"),
  )

  if (!anomalyRan && anomaly == null) {
    return {
      status: "SKIPPED",
      statusLabel: "SKIPPED",
      story:
        "Before looking at results, we normally check for Sample Ratio Mismatch — whether users were split evenly between groups. This check requires daily time-series data, which was not provided for this experiment. The randomization check was skipped.",
      detail: "No anomaly data available.",
    }
  }

  const checks = anomaly?.checks ?? []

  const srmFailedInChecks = checks.some(
    (c) =>
      !c.passed &&
      (c.name?.toLowerCase().includes("srm") ||
        c.name?.toLowerCase().includes("sample_ratio")),
  )

  const srmWarning = result.warnings?.find((w) => {
    const text = typeof w === "string" ? w : (w?.message ?? w?.text ?? "")
    return (
      text.toLowerCase().includes("imbalance") ||
      text.toLowerCase().includes("sample ratio")
    )
  })
  const srmText =
    typeof srmWarning === "string" ? srmWarning : (srmWarning?.message ?? srmWarning?.text ?? "")

  const imbalanceMatch = srmText.match(/control_n=(\d+),\s*treatment_n=(\d+)/)
  const ctrlTotal = imbalanceMatch
    ? parseInt(imbalanceMatch[1]) + parseInt(imbalanceMatch[2])
    : null
  const ctrlPct = imbalanceMatch
    ? ((parseInt(imbalanceMatch[1]) / ctrlTotal) * 100).toFixed(0)
    : null
  const trtPct = imbalanceMatch
    ? ((parseInt(imbalanceMatch[2]) / ctrlTotal) * 100).toFixed(0)
    : null

  const srmFailed = srmFailedInChecks || !!srmWarning

  const detailLines = checks.length
    ? checks.map(
        (c) =>
          `${c.passed ? "✓" : "✗"} ${c.name ?? "check"} — ${c.passed ? "passed" : "FAILED"}${
            c.score != null ? ` — score: ${Number(c.score).toFixed(3)}` : ""
          }${c.severity ? ` — severity: ${c.severity}` : ""}`,
      )
    : ["No checks data."]

  if (srmFailed) {
    const srmStory = imbalanceMatch
      ? `A critical problem was detected before we even look at results: Sample Ratio Mismatch (SRM). We expected a 50/50 split but observed ${ctrlPct}% vs ${trtPct}%. This means the randomization may be broken. Results below cannot be fully trusted.`
      : "A critical problem was detected before we even look at results: Sample Ratio Mismatch (SRM). We expected an even split between groups but observed a suspicious imbalance. This means the randomization may be broken. Results below cannot be fully trusted."
    return {
      status: "FAIL",
      statusLabel: "FAIL",
      story: srmStory,
      detail: [srmText || "SRM detected in warnings", ...detailLines].join("\n"),
    }
  }

  return {
    status: "PASS",
    statusLabel: "PASS",
    story:
      "Before looking at results, we checked whether the experiment ran correctly. We ran four validity checks on the daily data: sample ratio mismatch, variance stability, outlier detection, and stationarity. All checks passed — the data looks clean.",
    detail: detailLines.join("\n"),
  }
}

function buildAct2(result, cuped, bayesian) {
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

  let status, statusLabel, mainStory

  if (isSignificant) {
    status = "PASS"
    statusLabel = "SIGNIFICANT"
    mainStory =
      `We ran a ${testName} comparing the two groups. ` +
      `The control group measured ${controlFmt} and the treatment group measured ${treatmentFmt} — ` +
      `a difference of ${liftAbsFmt} (${liftPctFmt}% relative lift). ` +
      `The p-value (p=${pValueFmt}) is below the 5% threshold, which means there is less than a 5% chance this difference is random noise. ` +
      `The 95% confidence interval (${ciLowFmt} to ${ciHighFmt}) tells us the true effect is most likely somewhere in that range. ` +
      `This result is statistically significant.`
  } else {
    status = isUnderpowered ? "WARN" : "INFO"
    statusLabel = isUnderpowered ? "UNDERPOWERED" : "NOT YET SIGNIFICANT"
    mainStory =
      `We ran a ${testName} comparing the two groups. ` +
      `The control group measured ${controlFmt} and the treatment group measured ${treatmentFmt} — ` +
      `an observed difference of ${liftAbsFmt} (${liftPctFmt}% relative lift). ` +
      `However, the p-value (p=${pValueFmt}) is above the 5% threshold. ` +
      `This means the observed difference could plausibly be random variation — we do not have enough evidence yet to call this real.` +
      (plainEnglish ? " " + plainEnglish : "")
  }

  let cupedPara = null
  if (cuped && Number(cuped.variance_reduction_pct) <= 5 && Number(cuped.variance_reduction_pct) >= 0) {
    // CUPED ran but variance reduction was negligible — explain why honestly
    const reduction = Number(cuped.variance_reduction_pct).toFixed(1)
    const correlation = Number(cuped.correlation_pre_post).toFixed(2)
    const isBinaryLimitation = Math.abs(Number(cuped.correlation_pre_post)) < 0.1
    cupedPara = isBinaryLimitation
      ? `We ran CUPED (Controlled-experiment Using Pre-Experiment Data) but variance reduction was minimal (${reduction}%). ` +
        `This is expected when the pre-experiment covariate is binary (0 or 1) — two binary variables have a mathematical correlation ceiling that limits CUPED's effectiveness. ` +
        `To get meaningful variance reduction here, you would need a continuous pre-experiment covariate such as number of sessions, total spend, or page views in the 30 days before the experiment.`
      : `We ran CUPED but variance reduction was minimal (${reduction}%, correlation=${correlation}). ` +
        `The pre-experiment covariate has low predictive power for this outcome, so CUPED had little effect. ` +
        `A stronger covariate — one more directly related to the outcome — would give better results.`
  } else if (cuped && Number(cuped.variance_reduction_pct) > 5) {
    const rawP = cuped.unadjusted_test_result?.p_value
    const adjP = cuped.adjusted_test_result?.p_value
    const reduction = Number(cuped.variance_reduction_pct).toFixed(1)
    const correlation = Number(cuped.correlation_pre_post).toFixed(2)

    let decisionText
    if (rawP != null && adjP != null && rawP >= 0.05 && adjP < 0.05) {
      decisionText = `This changed the decision: without CUPED, p=${rawP.toFixed(4)} — not significant. With CUPED, p=${adjP.toFixed(4)} — significant. CUPED revealed a real effect that noise was hiding.`
    } else if (rawP != null && adjP != null && rawP < 0.05 && adjP < 0.05) {
      decisionText = `Without CUPED: p=${rawP.toFixed(4)}. With CUPED: p=${adjP.toFixed(4)}. The result was already significant, but CUPED tightened the confidence interval.`
    } else {
      decisionText = `Without CUPED: p=${rawP?.toFixed(4) ?? "?"}. With CUPED: p=${adjP?.toFixed(4) ?? "?"}. The result is not yet significant even with variance reduction — more data is needed.`
    }

    cupedPara =
      `We also ran CUPED (Controlled-experiment Using Pre-Experiment Data) — a variance reduction technique that uses each user's behavior before the experiment to remove noise from the measurement. ` +
      `The pre-experiment data had a correlation of ${correlation} with the outcome, giving ${reduction}% variance reduction. ${decisionText}`
  }

  let bayesianPara = null
  if (bayesian) {
    const prob = bayesian.prob_treatment_better
    let evidenceText
    if (prob >= 0.95) {
      evidenceText = "This is strong evidence for treatment."
    } else if (prob >= 0.80) {
      evidenceText = "This is moderate evidence for treatment."
    } else if (prob >= 0.50) {
      evidenceText = "Weak evidence — the direction looks positive but certainty is low."
    } else {
      evidenceText = "The evidence actually favors control."
    }

    bayesianPara =
      `We also ran a Bayesian analysis alongside the frequentist test. While the frequentist p-value asks 'how unlikely is this result if there's no effect?', Bayesian analysis asks 'given this data, what's the probability treatment is actually better?' ` +
      `Bayesian result: ${(prob * 100).toFixed(1)}% probability that treatment is better than control. ${evidenceText} ${bayesian.interpretation}`
  }

  const story =
    cupedPara || bayesianPara ? (
      <>
        <p style={{ margin: "0 0 8px 0" }}>{mainStory}</p>
        {cupedPara && (
          <p style={{ margin: bayesianPara ? "0 0 8px 0" : 0 }}>{cupedPara}</p>
        )}
        {bayesianPara && <p style={{ margin: 0 }}>{bayesianPara}</p>}
      </>
    ) : mainStory

  const detail = [
    `test type: ${testName}`,
    `p-value: ${pValueFmt}`,
    `confidence interval: ${ciLowFmt} to ${ciHighFmt}`,
    `lift (absolute): ${liftAbsFmt}`,
    `lift (relative): ${liftPctFmt}%`,
    `alpha threshold: 5% (0.05)`,
    cuped
      ? `cuped: variance reduction ${Number(cuped.variance_reduction_pct).toFixed(1)}%, correlation ${Number(cuped.correlation_pre_post).toFixed(2)}`
      : null,
    bayesian
      ? `bayesian: P(treatment > control) = ${(bayesian.prob_treatment_better * 100).toFixed(1)}%`
      : null,
  ]
    .filter(Boolean)
    .join("\n")

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

function buildAct4(result, techniques) {
  const { novelty } = result

  const noveltyRan = techniques?.ran?.some((t) => t.toLowerCase().includes("novelty"))
  const noveltySkippedEntry = techniques?.skipped?.find((t) =>
    t.name?.toLowerCase().includes("novelty"),
  )

  if (!noveltyRan && !novelty) {
    if (noveltySkippedEntry) {
      return {
        status: "SKIPPED",
        statusLabel: "SKIPPED",
        story: `Novelty detection requires daily time-series data. ${noveltySkippedEntry.how_to_enable}`,
        detail: `Reason: ${noveltySkippedEntry.reason}\nWhat it would show: ${noveltySkippedEntry.what_it_would_show}`,
      }
    }
    return {
      status: "SKIPPED",
      statusLabel: "SKIPPED",
      story:
        "Novelty detection requires daily time-series data showing how the treatment effect changes day by day. This data was not provided, so the check was skipped. If you upload daily aggregate data alongside subject rows, Axiom can automatically check whether effects are holding steady or fading.",
      detail: "No novelty data available.",
    }
  }

  if (noveltyRan && !novelty) {
    return {
      status: "PASS",
      statusLabel: "STABLE",
      story:
        "The treatment effect appears stable over time — no significant decay was detected. The lift observed in early days has held through the experiment window, which increases confidence that this is a genuine sustained effect rather than early excitement.",
      detail: "Novelty detection ran; no decay pattern found.",
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

function buildAct5(result, techniques) {
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
      <p style={{ margin: recommendation || techniques ? "0 0 8px 0" : 0 }}>{body}</p>
      {recommendation && (
        <p style={{ margin: techniques ? "0 0 8px 0" : 0 }}>
          <strong style={{ color: "var(--color-text-primary)", fontWeight: 600 }}>
            Recommendation:
          </strong>{" "}
          {recommendation}
        </p>
      )}
      <TechniquesChecklist techniques={techniques} />
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

export default function AnalysisNarrative({ result, experiment, bayesian, cuped, techniques, sequential }) {
  if (!result) return null

  const acts = [
    { step: "01", title: "Checking the randomization",      ...buildAct1(result, techniques) },
    { step: "02", title: "What the data showed",             ...buildAct2(result, cuped, bayesian) },
    { step: "03", title: "Who does it actually help?",       ...buildAct3(result) },
    { step: "04", title: "Is the effect stable over time?",  ...buildAct4(result, techniques) },
    { step: "05", title: "The verdict",                      ...buildAct5(result, techniques) },
  ]

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 24 }}>
      {acts.map((act) => (
        <Act key={act.step} {...act} />
      ))}
    </div>
  )
}
