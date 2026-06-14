import { useState, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'
import { API_BASE } from '../../config/api'

// ── helpers ───────────────────────────────────────────────────────────────────

const CRITEO_BLURB =
  'The data comes from the Criteo Uplift Modeling Dataset (f0–f11) — a real randomized experiment run by Criteo, an ad technology company, with 14 million rows and 12 anonymized behavioral signals. We use a 10,000 row sample for this demo: the full dataset would exceed the compute limits of this free-tier environment, and at 14M rows statistical significance becomes trivial (p → 0 for any difference). In production, the stats engine runs on the full dataset while the ML pipeline samples for efficiency — a standard pattern used by Statsig, Optimizely, and most experimentation platforms. Feature names are anonymized for privacy but the experiment and outcomes are real.'

function isCriteo(name = '') {
  return /saas|onboarding/i.test(name)
}

function fmtMde(mde, expType) {
  if (mde == null) return null
  if (expType === 'proportion') {
    const pp = mde * 100
    const s = pp % 1 === 0 ? pp.toFixed(0) : pp.toFixed(1)
    return `${s} percentage point${pp === 1 ? '' : 's'}`
  }
  const s = mde % 1 === 0 ? mde.toFixed(0) : mde.toFixed(2)
  return `${s} units`
}

function fmtPct(v) {
  if (v == null) return null
  const pct = v * 100
  return `${pct % 1 === 0 ? pct.toFixed(0) : pct.toFixed(1)}%`
}

function getTreatmentName(name = '') {
  const n = name.toLowerCase()
  if (/checkout|e-commerce|ecommerce/.test(n)) return 'the new checkout'
  if (/saas|onboarding/.test(n)) return 'the onboarding checklist'
  if (/marketplace|fee|seller/.test(n)) return 'the fee reduction'
  return 'the treatment'
}

function getMetricName(expType, name = '') {
  const n = name.toLowerCase()
  if (expType === 'proportion') {
    if (/checkout|e-commerce|ecommerce/.test(n)) return 'checkout conversion rate'
    return 'conversion rate'
  }
  if (/saas|onboarding/.test(n)) return 'activation score'
  if (/marketplace|seller|fee/.test(n)) return 'GMV per seller'
  return 'average outcome'
}

function computeSampleSize(baselineProp, mde) {
  if (baselineProp == null || mde == null || mde === 0) return null
  const p = baselineProp
  // z_α/2=1.96 (two-tailed α=0.05), z_β=0.84 (80% power)
  return Math.ceil(2 * Math.pow(1.96 + 0.84, 2) * p * (1 - p) / Math.pow(mde, 2))
}

function getDemoContent(name = '') {
  const n = name.toLowerCase()
  if (/checkout|e-commerce|ecommerce/.test(n)) {
    return {
      label: '🧪 Synthetic — designed to show clean HTE',
      title: 'What this demo shows',
      story:
        'This experiment demonstrates a CLEAN result with HETEROGENEOUS TREATMENT EFFECTS. The overall conversion lift is real and significant — but the average conceals that mobile users respond 5× better than desktop users. The HTE analysis finds this automatically.\n\nThe pre-experiment covariate is binary (0/1), which limits CUPED variance reduction — this is intentional and honest. Binary covariates have a mathematical correlation ceiling that makes CUPED ineffective for proportion experiments.\n\nThe outcome is binary (converted = 1, didn\'t = 0). This is the most common A/B test outcome type.\n\nDistributions used: device_type (40% mobile, 20% tablet, 40% desktop — realistic for mid-size e-commerce). cart_value uses lognormal distribution (median ~$33, long tail to high values — matches real purchase data). user_tenure is exponential (most users are newer, long tail of veterans).\n\nTreatment effect was designed to be heterogeneous: mobile users benefit most from a simplified checkout (+5pp), tablet users moderately (+2pp), desktop barely (+0.5pp). This heterogeneity is realistic — simplified checkouts disproportionately help small-screen users.',
    }
  }
  if (/saas|onboarding/.test(n)) {
    return {
      label: '🧪 Synthetic — designed to show CUPED flip',
      title: 'What this demo shows',
      story:
        'This experiment demonstrates CUPED CHANGING A BUSINESS DECISION. The standard frequentist test says NOT significant (p=0.775). After CUPED variance reduction (39.6%), the adjusted result is SIGNIFICANT (p=0.034). Without CUPED, a team would abandon a feature that genuinely works.\n\nThe outcome is a continuous activation score (0-100) because CUPED requires a continuous pre-experiment covariate to achieve meaningful variance reduction. Binary outcomes hit a correlation ceiling that makes CUPED ineffective.\n\nWhy 10,000 rows and not the full 14 million from Criteo? Three reasons: (1) The free hosting tier (Render) has 512MB RAM — XGBoost and K-means on 14M rows would crash it. (2) At 14M rows, p-values approach zero for any difference, making significance trivial and uninformative. (3) 10,000 rows creates realistic statistical tension — the experiment is borderline without CUPED, which is exactly the scenario we want to demonstrate.\n\nThe outcome (activation score 0-100) is continuous, not binary. This matters because: CUPED works much better with continuous outcomes (correlation can reach 0.6-0.9 vs 0.1-0.3 for binary). The t-test is the right test for continuous means. Bayesian analysis uses the Normal-Normal model instead of Beta-Binomial.',
    }
  }
  if (/marketplace|fee|seller/.test(n)) {
    return {
      label: '🧪 Synthetic — designed to show broken experiment',
      title: 'What this demo shows',
      story:
        'This experiment demonstrates a BROKEN EXPERIMENT that looks like a win. Two problems make the result untrustworthy:\n\n1. Sample Ratio Mismatch (55/45 split instead of 50/50) — larger sellers self-selected into treatment, creating selection bias.\n\n2. Novelty effect — sellers rushed to list items when fees dropped, creating a temporary spike that will fade.\n\nSRM detection catches this before you look at results. The correct decision is to run a properly randomized experiment before making a permanent pricing change.\n\nThe outcome is continuous GMV per seller (dollars). Distribution: lognormal base (most sellers have moderate GMV, a few power sellers have very high GMV) with 3% outliers at 8× the normal rate — realistic for marketplace data.\n\nThe broken randomization (55/45 split) was designed to simulate self-selection: larger, more experienced sellers heard about the fee reduction through their network and found ways to opt into treatment. This is the most common real-world cause of SRM in marketplace experiments.',
    }
  }
  return {
    label: '🧪 Synthetic demonstration',
    title: 'Synthetic data',
    story:
      'This analysis uses generated data. Results demonstrate how the pipeline works but are not measurements of a real experiment.',
  }
}

// ── sub-components ────────────────────────────────────────────────────────────

function Section({ label, children, accentColor, isFirst }) {
  return (
    <div
      style={{
        padding: '18px 24px',
        borderLeft: `3px solid ${accentColor}`,
        borderTop: isFirst ? 'none' : '1px solid var(--color-border-subtle)',
      }}
    >
      <p
        style={{
          fontSize: 11,
          textTransform: 'uppercase',
          letterSpacing: '0.12em',
          color: 'var(--color-text-muted)',
          marginBottom: 6,
          fontFamily: 'inherit',
        }}
      >
        {label}
      </p>
      <div
        style={{
          fontSize: 13,
          color: 'var(--color-text-secondary)',
          lineHeight: 1.7,
        }}
      >
        {children}
      </div>
    </div>
  )
}

function InfoBox({ children }) {
  return (
    <div
      style={{
        background: 'rgba(245,158,11,0.08)',
        border: '1px solid rgba(245,158,11,0.2)',
        borderRadius: 6,
        padding: '10px 14px',
        marginTop: 10,
        fontSize: 12,
        color: 'var(--color-text-secondary)',
        lineHeight: 1.6,
      }}
    >
      {children}
    </div>
  )
}

function RuleItem({ children }) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 8,
        alignItems: 'flex-start',
        marginTop: 8,
      }}
    >
      <span style={{ color: 'var(--color-text-muted)', flexShrink: 0, marginTop: 1 }}>○</span>
      <p style={{ margin: 0, fontSize: 12, color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>
        {children}
      </p>
    </div>
  )
}

function DemoCallout({ label, title, story }) {
  return (
    <div
      style={{
        background: 'rgba(245,158,11,0.06)',
        border: '1px solid rgba(245,158,11,0.25)',
        borderRadius: 8,
        padding: '14px 18px',
        marginBottom: 4,
      }}
    >
      <p
        style={{
          margin: '0 0 6px 0',
          fontSize: 11,
          textTransform: 'uppercase',
          letterSpacing: '0.1em',
          color: 'var(--color-accent-amber)',
          fontWeight: 600,
        }}
      >
        {label}
      </p>
      <p
        style={{
          margin: '0 0 8px 0',
          fontSize: 13,
          fontWeight: 500,
          color: 'var(--color-text-primary)',
        }}
      >
        {title}
      </p>
      <p
        style={{
          margin: 0,
          fontSize: 12,
          color: 'var(--color-text-secondary)',
          lineHeight: 1.7,
          whiteSpace: 'pre-line',
        }}
      >
        {story}
      </p>
    </div>
  )
}

// ── main component ────────────────────────────────────────────────────────────

export default function ExperimentContext({ experiment, dataSource }) {
  const [collapsed, setCollapsed] = useState(false)
  const [counts, setCounts] = useState({ total: null, control: null, treatment: null })

  useEffect(() => {
    if (dataSource !== 'real' || !experiment?.id) return
    fetch(`${API_BASE}/api/v1/experiments/${experiment.id}/subject-counts`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.data) setCounts(d.data)
      })
      .catch(() => {})
  }, [dataSource, experiment?.id])

  const expType = experiment?.experiment_type ?? 'proportion'
  const isReal = dataSource === 'real'
  const topAccent = isReal ? 'var(--color-accent-blue)' : 'var(--color-accent-amber)'
  const sectionAccent = isReal ? 'var(--color-accent-blue)' : 'var(--color-accent-amber)'

  // ── Section 1: The Dataset ────────────────────────────────────────────────

  let datasetContent
  if (isReal) {
    const { total, control, treatment } = counts
    let datasetParagraph
    if (total != null && control != null && treatment != null) {
      datasetParagraph = `This analysis runs on ${total.toLocaleString()} real subjects — ${control.toLocaleString()} in control and ${treatment.toLocaleString()} in treatment — uploaded directly into Axiom.`
    } else if (total != null) {
      datasetParagraph = `This analysis runs on ${total.toLocaleString()} real subjects uploaded directly into Axiom.`
    } else {
      datasetParagraph = 'This analysis uses real uploaded subject-level data stored in Axiom.'
    }
    datasetContent = (
      <>
        <p style={{ margin: 0 }}>{datasetParagraph}</p>
        {isCriteo(experiment?.name) && (
          <p style={{ margin: '10px 0 0' }}>{CRITEO_BLURB}</p>
        )}
      </>
    )
  } else {
    const baseline = experiment?.baseline_metric
    const mdeVal = experiment?.mde
    const trafficN = experiment?.daily_traffic_estimate

    let p1
    if (expType === 'proportion') {
      const baselineStr =
        baseline != null ? `${(baseline * 100).toFixed(1)}%` : 'the configured baseline'
      const mdeStr2 = mdeVal != null ? fmtMde(mdeVal, expType) : 'the target lift'
      const trafficStr = trafficN != null ? trafficN.toLocaleString() : 'an estimated number of'
      p1 = `No real data has been uploaded yet. The numbers below are simulated from this experiment's configuration — a baseline conversion rate of ${baselineStr} with a target lift of ${mdeStr2}. Axiom generates ${trafficStr} users per group using these parameters to show you what results would look like if the hypothesized effect is real. This is a preview, not a measurement.`
    } else {
      const baselineStr =
        baseline != null
          ? baseline % 1 === 0 ? baseline.toFixed(0) : baseline.toFixed(2)
          : 'the configured baseline'
      const mdeStr2 = mdeVal != null ? fmtMde(mdeVal, expType) : 'the target lift'
      const trafficStr = trafficN != null ? trafficN.toLocaleString() : 'an estimated number of'
      p1 = `No real data has been uploaded yet. The numbers below are simulated from this experiment's configuration — a baseline average of ${baselineStr} with a target lift of ${mdeStr2}. Axiom generates ${trafficStr} users per group drawn from a normal distribution around these values. This is a preview, not a measurement.`
    }

    const p2 =
      expType === 'proportion'
        ? 'To run this on real data, upload a CSV with one row per user. Each row represents one subject in the experiment.'
        : 'To run this on real data, upload a CSV with one row per subject. Each row represents one unit in the experiment (e.g. one seller, one session, one user).'

    const outcomeDesc =
      expType === 'proportion'
        ? '1 if converted, 0 if not'
        : 'the numeric value (e.g. revenue in dollars, GMV per seller)'
    const requiredCols = [
      { name: 'subject_id', desc: 'a unique identifier for each user or unit (e.g. user_123, session_456)' },
      { name: 'variant', desc: '0 for control group, 1 for treatment group' },
      { name: 'outcome', desc: outcomeDesc },
    ]

    const expName = (experiment?.name ?? '').toLowerCase()
    let optionalCols = null
    let optionalIsGeneric = false
    if (/checkout|e-commerce|ecommerce/.test(expName)) {
      optionalCols = [
        { name: 'device_type', desc: '0=mobile, 1=tablet, 2=desktop' },
        { name: 'user_tenure_days', desc: 'how long the user has been a customer' },
        { name: 'cart_value', desc: 'value of items in cart before checkout' },
        { name: 'is_returning_user', desc: '1=returning, 0=new' },
      ]
    } else if (/saas|onboarding/.test(expName)) {
      optionalCols = [
        { name: 'company_size', desc: 'number of employees' },
        { name: 'plan_type', desc: '0=free, 1=trial, 2=paid' },
        { name: 'days_since_signup', desc: '' },
        { name: 'feature_usage_count', desc: '' },
      ]
    } else if (/marketplace|seller|fee/.test(expName)) {
      optionalCols = [
        { name: 'seller_tenure_days', desc: '' },
        { name: 'avg_listing_price', desc: '' },
        { name: 'listings_count', desc: '' },
        { name: 'category_id', desc: '' },
      ]
    } else {
      optionalIsGeneric = true
    }

    const colRowStyle = { display: 'flex', gap: 8, alignItems: 'baseline', marginBottom: 4 }
    const colNameStyle = { fontFamily: 'DM Mono, monospace', fontSize: 12, color: 'var(--color-text-data)', flexShrink: 0 }
    const colDescStyle = { fontSize: 12, color: 'var(--color-text-secondary)' }
    const sectionLabelStyle = {
      fontSize: 11,
      textTransform: 'uppercase',
      letterSpacing: '0.1em',
      color: 'var(--color-text-muted)',
      margin: '0 0 8px 0',
    }

    datasetContent = (
      <div>
        <p style={{ margin: 0 }}>{p1}</p>
        <p style={{ margin: '10px 0 0' }}>{p2}</p>
        <div
          style={{
            background: 'var(--color-bg-elevated)',
            borderRadius: 6,
            padding: '12px 16px',
            marginTop: 12,
          }}
        >
          <p style={sectionLabelStyle}>Required columns</p>
          {requiredCols.map((col) => (
            <div key={col.name} style={colRowStyle}>
              <span style={colNameStyle}>{col.name}</span>
              <span style={colDescStyle}>— {col.desc}</span>
            </div>
          ))}
          <div style={{ borderTop: '1px solid var(--color-border-subtle)', margin: '10px 0' }} />
          <p style={sectionLabelStyle}>Optional columns</p>
          {optionalIsGeneric ? (
            <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: 0 }}>
              Any numeric columns beyond the required three will be used as features for ML
              analysis (heterogeneous treatment effects and segment discovery).
            </p>
          ) : (
            optionalCols?.map((col) => (
              <div key={col.name} style={colRowStyle}>
                <span style={colNameStyle}>{col.name}</span>
                {col.desc && <span style={colDescStyle}>— {col.desc}</span>}
              </div>
            ))
          )}
          <p style={{ fontSize: 12, color: 'var(--color-text-muted)', margin: '10px 0 0', fontStyle: 'italic' }}>
            The more optional features you provide, the richer the segment and treatment effect
            analysis.
          </p>
        </div>
      </div>
    )
  }

  // ── Section 2: The Business Goal ──────────────────────────────────────────

  const treatmentName = getTreatmentName(experiment?.name)
  const metricName = getMetricName(expType, experiment?.name)
  const mdeVal = experiment?.mde
  const mdeFormatted = fmtMde(mdeVal, expType)

  const nullHyp = `Null hypothesis (H₀): ${treatmentName} has no effect on ${metricName}.`
  const altHyp =
    expType === 'proportion'
      ? mdeFormatted
        ? `Alternative hypothesis (H₁): ${treatmentName} increases ${metricName} by at least ${mdeFormatted}.`
        : `Alternative hypothesis (H₁): ${treatmentName} increases ${metricName}.`
      : mdeFormatted
      ? `Alternative hypothesis (H₁): ${treatmentName} changes ${metricName} by at least ${mdeFormatted}.`
      : `Alternative hypothesis (H₁): ${treatmentName} changes ${metricName}.`

  const descriptionText = experiment?.description || null
  const hypothesisText = experiment?.hypothesis || null

  const subLabelStyle = {
    fontSize: 11,
    textTransform: 'uppercase',
    letterSpacing: '0.1em',
    color: 'var(--color-text-muted)',
    margin: '0 0 4px',
  }

  const businessGoalContent = (
    <div>
      {descriptionText && (
        <div style={{ marginBottom: 14 }}>
          <p style={subLabelStyle}>What we're changing</p>
          <p style={{ margin: 0 }}>{descriptionText}</p>
        </div>
      )}
      <div style={{ marginBottom: hypothesisText ? 14 : 0 }}>
        <p style={subLabelStyle}>The Hypothesis</p>
        <p style={{ margin: '0 0 3px', fontFamily: 'DM Mono, monospace', fontSize: 12, color: 'var(--color-text-secondary)' }}>
          {nullHyp}
        </p>
        <p style={{ margin: 0, fontFamily: 'DM Mono, monospace', fontSize: 12, color: 'var(--color-text-secondary)' }}>
          {altHyp}
        </p>
      </div>
      {hypothesisText && (
        <p style={{ margin: 0, fontStyle: 'italic', color: 'var(--color-text-muted)', fontSize: 12 }}>
          "{hypothesisText}"
        </p>
      )}
    </div>
  )

  // ── Section 3: The Statistical Design ────────────────────────────────────

  const alpha = experiment?.alpha
  const power = experiment?.power
  const traffic = experiment?.daily_traffic_estimate
  const alphaStr = fmtPct(alpha)
  const powerStr = fmtPct(power)
  const alphaPct =
    alpha != null
      ? `${(alpha * 100) % 1 === 0 ? (alpha * 100).toFixed(0) : (alpha * 100).toFixed(1)}`
      : null
  const powerPct =
    power != null
      ? `${(power * 100) % 1 === 0 ? (power * 100).toFixed(0) : (power * 100).toFixed(1)}`
      : null
  const missPct = powerPct != null ? (100 - parseFloat(powerPct)).toFixed(0) : null

  const sampleN = expType === 'proportion' ? computeSampleSize(experiment?.baseline_metric, mdeVal) : null

  const paramLabelStyle = { fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--color-text-muted)', margin: '0 0 3px' }
  const paramValueStyle = { margin: '0 0 2px', fontFamily: 'DM Mono, monospace', fontSize: 12, color: 'var(--color-text-data)' }
  const paramExplainStyle = { margin: 0, fontSize: 12, color: 'var(--color-text-secondary)', lineHeight: 1.6 }
  const paramRowStyle = { marginBottom: 14 }

  const designContent = (
    <div>
      <div style={paramRowStyle}>
        <p style={paramLabelStyle}>Experiment type</p>
        <p style={paramValueStyle}>
          {expType === 'proportion' ? 'Proportion experiment' : 'Mean experiment'}
        </p>
        {expType === 'proportion' ? (
          <>
            <p style={{ ...paramExplainStyle, marginBottom: 6 }}>
              <strong style={{ color: 'var(--color-text-primary)' }}>Outcome type: Binary (0 or 1)</strong>
            </p>
            <p style={{ ...paramExplainStyle, marginBottom: 6 }}>
              Each user either converts or doesn't — there is no in-between. This is the most common A/B test outcome.
            </p>
            <p style={{ ...paramExplainStyle, marginBottom: 6 }}>
              Examples: purchased vs didn't purchase, clicked vs didn't click, signed up vs didn't sign up.
            </p>
            <p style={paramExplainStyle}>
              Test used: Z-test for proportions. Works because with large samples, the distribution of a proportion approaches normal (Central Limit Theorem). We compare p₁ vs p₂ where p = conversions / total users.
            </p>
          </>
        ) : (
          <>
            <p style={{ ...paramExplainStyle, marginBottom: 6 }}>
              <strong style={{ color: 'var(--color-text-primary)' }}>Outcome type: Continuous (numeric score or value)</strong>
            </p>
            <p style={{ ...paramExplainStyle, marginBottom: 6 }}>
              Each user gets a numeric measurement — a score, revenue amount, duration, or any other number. This allows more nuance than binary outcomes.
            </p>
            <p style={{ ...paramExplainStyle, marginBottom: 6 }}>
              Examples: activation score (0-100), revenue per user ($), session duration (seconds), items per order.
            </p>
            <p style={{ ...paramExplainStyle, marginBottom: 6 }}>
              Test used: Welch's t-test. Unlike Student's t-test, Welch's doesn't assume equal variance between groups — which is important because treatment effects often change variance as well as mean.
            </p>
            <p style={paramExplainStyle}>
              Note: You could turn a continuous outcome into binary by picking a threshold (e.g. 'activated = score ≥ 60') but you lose information by doing so. The continuous version is more statistically powerful.
            </p>
          </>
        )}
      </div>

      {mdeFormatted && (
        <div style={paramRowStyle}>
          <p style={paramLabelStyle}>Minimum detectable effect</p>
          <p style={paramValueStyle}>{mdeFormatted}</p>
          <p style={paramExplainStyle}>
            This is the smallest improvement worth shipping. Below this threshold, the change
            isn't worth the engineering and business cost.
          </p>
        </div>
      )}

      {alphaStr && alphaPct && (
        <div style={paramRowStyle}>
          <p style={paramLabelStyle}>Significance threshold</p>
          <p style={paramValueStyle}>{alphaStr} (α = {alphaPct}%)</p>
          <p style={paramExplainStyle}>
            We accept a {alphaPct}% chance of a false positive — meaning {alphaPct} times out of
            100, we'd call a result significant when it's actually random noise. 5% is the industry
            standard for most product experiments.
          </p>
        </div>
      )}

      {powerStr && powerPct && (
        <div style={paramRowStyle}>
          <p style={paramLabelStyle}>Statistical power</p>
          <p style={paramValueStyle}>{powerStr}</p>
          <p style={paramExplainStyle}>
            If the treatment truly works, we have a {powerPct}% chance of detecting it. The
            remaining {missPct}% is the chance we miss a real effect (Type II error). 80% power is
            the accepted tradeoff between sample size and sensitivity.
          </p>
        </div>
      )}

      {sampleN && (
        <div style={{ ...paramRowStyle, marginBottom: 0 }}>
          <p style={paramLabelStyle}>Required sample</p>
          <p style={paramValueStyle}>~{sampleN.toLocaleString()} users per group</p>
          {traffic ? (
            <p style={paramExplainStyle}>
              At {traffic.toLocaleString()} users/day: run for at least{' '}
              {Math.ceil((sampleN * 2) / traffic)} days.
            </p>
          ) : null}
        </div>
      )}
    </div>
  )

  // ── Section 4: How We're Monitoring ──────────────────────────────────────

  const monitoringContent = (
    <div>
      <p style={{ margin: 0 }}>A/B testing requires discipline during the run:</p>
      <InfoBox>
        <p style={{ margin: '0 0 4px', fontWeight: 500, color: 'var(--color-accent-amber)' }}>
          ⚠ Don't peek at p-values daily without sequential testing.
        </p>
        <p style={{ margin: 0 }}>
          Checking results every day and stopping when p &lt; 0.05 inflates your false positive
          rate from 5% to ~30%. This is called the peeking problem.
        </p>
        <p style={{ margin: '6px 0 0' }}>
          Axiom handles this automatically using O'Brien-Fleming sequential boundaries — which let
          you monitor results daily without penalty. The boundary starts strict (you need very
          strong evidence to stop early) and relaxes as the experiment matures.
        </p>
      </InfoBox>
      <div style={{ marginTop: 10 }}>
        <RuleItem>
          <strong style={{ color: 'var(--color-text-primary)' }}>
            Don't change experiment parameters mid-run
          </strong>
          <br />
          Changing traffic weights, eligibility rules, or the metric definition after launch
          invalidates the statistical guarantees.
        </RuleItem>
        <RuleItem>
          <strong style={{ color: 'var(--color-text-primary)' }}>Run for at least 7 days</strong>
          <br />
          Captures day-of-week effects. A checkout that performs differently on weekdays vs
          weekends needs at least one full week to average out.
        </RuleItem>
        <RuleItem>
          <strong style={{ color: 'var(--color-text-primary)' }}>Note external events</strong>
          <br />
          If a major event happened during your experiment (outage, holiday, competitor launch),
          note it. Axiom can't detect external events automatically.
        </RuleItem>
      </div>
    </div>
  )

  // ── Section 5: What This Demonstrates (synthetic only) ───────────────────

  const demoContent = !isReal ? getDemoContent(experiment?.name) : null

  // ── render ────────────────────────────────────────────────────────────────

  const headerLabel = isReal ? 'EXPERIMENT DESIGN' : 'EXPERIMENT DESIGN · SYNTHETIC DEMO'

  return (
    <div
      style={{
        background: 'var(--color-bg-card)',
        borderLeft: '1px solid var(--color-border-subtle)',
        borderRight: '1px solid var(--color-border-subtle)',
        borderBottom: '1px solid var(--color-border-subtle)',
        borderTop: `3px solid ${topAccent}`,
        borderRadius: 12,
        overflow: 'hidden',
        marginBottom: 28,
      }}
    >
      <div
        role="button"
        tabIndex={0}
        onClick={() => setCollapsed((c) => !c)}
        onKeyDown={(e) => e.key === 'Enter' && setCollapsed((c) => !c)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 24px',
          cursor: 'pointer',
          background: 'var(--color-bg-elevated)',
          borderBottom: collapsed ? 'none' : '1px solid var(--color-border-subtle)',
          userSelect: 'none',
        }}
      >
        <span
          style={{
            fontSize: 12,
            textTransform: 'uppercase',
            letterSpacing: '0.12em',
            color: 'var(--color-text-muted)',
          }}
        >
          {headerLabel}
        </span>
        <ChevronDown
          size={14}
          style={{
            color: 'var(--color-text-muted)',
            transform: collapsed ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s ease',
            flexShrink: 0,
          }}
        />
      </div>

      <div style={{ display: collapsed ? 'none' : 'block' }}>
        {isReal ? (
          <>
            <Section label="The Dataset" accentColor={sectionAccent} isFirst>
              {datasetContent}
            </Section>
            <Section label="The Business Goal" accentColor="var(--color-accent-blue)">
              {businessGoalContent}
            </Section>
            <Section label="The Statistical Design" accentColor="var(--color-accent-blue)">
              {designContent}
            </Section>
            <Section label="How We're Monitoring" accentColor="var(--color-accent-blue)">
              {monitoringContent}
            </Section>
          </>
        ) : (
          <>
            <Section label="What This Demonstrates" accentColor="var(--color-accent-amber)" isFirst>
              <DemoCallout {...demoContent} />
            </Section>
            <Section label="The Business Goal" accentColor="var(--color-accent-amber)">
              {businessGoalContent}
            </Section>
            <Section label="The Statistical Design" accentColor="var(--color-accent-amber)">
              {designContent}
            </Section>
            <Section label="How We're Monitoring" accentColor="var(--color-accent-amber)">
              {monitoringContent}
            </Section>
            <Section label="The Dataset" accentColor="var(--color-accent-amber)">
              {datasetContent}
            </Section>
          </>
        )}
      </div>
    </div>
  )
}
