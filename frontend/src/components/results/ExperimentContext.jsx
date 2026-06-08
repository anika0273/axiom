import { useState, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'

const API_BASE = 'http://localhost:8000'

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
  let datasetParagraph
  if (isReal) {
    const { total, control, treatment } = counts
    if (total != null && control != null && treatment != null) {
      datasetParagraph = `This analysis runs on ${total.toLocaleString()} real subjects — ${control.toLocaleString()} in control and ${treatment.toLocaleString()} in treatment — uploaded directly into Axiom.`
    } else if (total != null) {
      datasetParagraph = `This analysis runs on ${total.toLocaleString()} real subjects uploaded directly into Axiom.`
    } else {
      datasetParagraph = 'This analysis uses real uploaded subject-level data stored in Axiom.'
    }
  } else {
    datasetParagraph =
      "No real subject data has been uploaded for this experiment yet. The analysis below is a simulation — generated from the experiment’s configured baseline metric and minimum detectable effect. Upload a CSV to run this analysis on real data."
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
          <p style={{ margin: 0 }}>{datasetParagraph}</p>
          {isReal && isCriteo(experiment?.name) && (
            <p style={{ margin: '10px 0 0' }}>{CRITEO_BLURB}</p>
          )}
        </Section>

        <Section label="What We’re Testing" accentColor="var(--color-accent-blue)">
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

        <Section label="How It’s Set Up" accentColor="var(--color-accent-blue)">
          <p style={{ margin: 0 }}>{setupText}</p>
        </Section>
      </div>
    </div>
  )
}
