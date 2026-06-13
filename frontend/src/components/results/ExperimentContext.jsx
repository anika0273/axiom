import { useState, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'
import { API_BASE } from '../../config/api'

const CRITEO_BLURB =
  'The data comes from the Criteo Uplift Modeling Dataset (f0–f11) — a real randomized experiment run by Criteo, an ad technology company, with 14 million rows and 12 anonymized behavioral signals. Feature names are anonymized for privacy but the experiment and outcomes are real. This is a published benchmark dataset used in academic causal inference research.'

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
  const section1Accent = isReal ? 'var(--color-accent-blue)' : 'var(--color-accent-amber)'

  // ── Section 1: Dataset ────────────────────────────────────────────────────
  let datasetParagraph = ''
  if (isReal) {
    const { total, control, treatment } = counts
    if (total != null && control != null && treatment != null) {
      datasetParagraph = `This analysis runs on ${total.toLocaleString()} real subjects — ${control.toLocaleString()} in control and ${treatment.toLocaleString()} in treatment — uploaded directly into Axiom.`
    } else if (total != null) {
      datasetParagraph = `This analysis runs on ${total.toLocaleString()} real subjects uploaded directly into Axiom.`
    } else {
      datasetParagraph = 'This analysis uses real uploaded subject-level data stored in Axiom.'
    }
  }

  // Synthetic section — only built when dataSource !== 'real'
  let syntheticContent = null
  if (!isReal) {
    const baseline = experiment?.baseline_metric
    const mdeVal = experiment?.mde
    const trafficN = experiment?.daily_traffic_estimate

    // P1 — what the simulation is
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

    // P2 — what real data looks like
    const p2 =
      expType === 'proportion'
        ? 'To run this on real data, upload a CSV with one row per user. Each row represents one subject in the experiment.'
        : 'To run this on real data, upload a CSV with one row per subject. Each row represents one unit in the experiment (e.g. one seller, one session, one user).'

    // Required columns
    const outcomeDesc =
      expType === 'proportion'
        ? '1 if converted, 0 if not'
        : 'the numeric value (e.g. revenue in dollars, GMV per seller)'
    const requiredCols = [
      { name: 'subject_id', desc: 'a unique identifier for each user or unit (e.g. user_123, session_456)' },
      { name: 'variant', desc: '0 for control group, 1 for treatment group' },
      { name: 'outcome', desc: outcomeDesc },
    ]

    // Optional columns — experiment-specific
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

    syntheticContent = (
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

  // ── Section 2: Hypothesis ─────────────────────────────────────────────────
  const hypothesisText = experiment?.hypothesis || experiment?.description || null

  // ── Section 3: Setup ──────────────────────────────────────────────────────
  const mdeStr = fmtMde(experiment?.mde, expType)
  const alphaStr = fmtPct(experiment?.alpha)
  const powerStr = fmtPct(experiment?.power)
  const alphaPct =
    experiment?.alpha != null
      ? `${
          (experiment.alpha * 100) % 1 === 0
            ? (experiment.alpha * 100).toFixed(0)
            : (experiment.alpha * 100).toFixed(1)
        }`
      : null
  const traffic = experiment?.daily_traffic_estimate
  const expTypeLabel = expType === 'proportion' ? 'proportion' : 'mean'

  let setupText = `This is a ${expTypeLabel} experiment`
  if (mdeStr) setupText += ` targeting a minimum detectable effect (MDE) of ${mdeStr}`
  setupText += '.'
  if (alphaStr && alphaPct) {
    setupText += ` The significance threshold (α) is set to ${alphaStr} — meaning we require less than a ${alphaPct}% chance the result is random before calling it real.`
  }
  if (powerStr) {
    setupText += ` We targeted ${powerStr} statistical power, which controls how likely we are to detect a real effect when one exists.`
  }
  if (traffic) {
    setupText += ` The estimated daily traffic is ${traffic.toLocaleString()} users.`
  }

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
      {/* Toggle header */}
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
          Experiment Context
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

      {/* Collapsible sections */}
      <div style={{ display: collapsed ? 'none' : 'block' }}>
        <Section label="The Dataset" accentColor={section1Accent} isFirst>
          {isReal ? (
            <>
              <p style={{ margin: 0 }}>{datasetParagraph}</p>
              {isCriteo(experiment?.name) && (
                <p style={{ margin: '10px 0 0' }}>{CRITEO_BLURB}</p>
              )}
            </>
          ) : (
            syntheticContent
          )}
        </Section>

        <Section label="What We're Testing" accentColor="var(--color-accent-blue)">
          {hypothesisText ? (
            <p style={{ margin: 0 }}>
              <span style={{ color: 'var(--color-text-muted)', marginRight: 4 }}>
                The hypothesis for this experiment:
              </span>
              {hypothesisText}
            </p>
          ) : (
            <p style={{ margin: 0 }}>No hypothesis has been recorded for this experiment.</p>
          )}
        </Section>

        <Section label="How It's Set Up" accentColor="var(--color-accent-blue)">
          <p style={{ margin: 0 }}>{setupText}</p>
        </Section>
      </div>
    </div>
  )
}
