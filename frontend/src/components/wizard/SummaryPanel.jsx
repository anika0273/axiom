import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Button from '../ui/Button'

function KeyNumber({ label, value, sub }) {
  return (
    <div className="p-3 bg-card rounded-lg border border-subtle">
      <p className="text-xs text-muted mb-1">{label}</p>
      <p className="font-mono text-data font-bold text-lg leading-none">{value}</p>
      {sub && <p className="text-xs text-muted mt-1.5 leading-snug">{sub}</p>}
    </div>
  )
}

export default function SummaryPanel({ state, sampleSizeResult }) {
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(null)
  const navigate = useNavigate()

  const ss = sampleSizeResult?.ss
  const rt = sampleSizeResult?.runtime

  async function handleCreate() {
    setSubmitting(true)
    setSubmitError(null)

    const isProportion = state.primaryMetricType === 'proportion'
    const baselineRaw = parseFloat(state.baseline) || 0
    const payload = {
      name: state.name,
      description: state.hypothesis || undefined,
      hypothesis: state.hypothesis || undefined,
      experiment_type: state.primaryMetricType || 'proportion',
      // Proportion baselines are stored as % strings ("4" → 0.04); mean/ratio
      // baselines are absolute values and should be passed through directly.
      baseline_metric: isProportion ? baselineRaw / 100 : baselineRaw,
      // Slider stores MDE as percentage points (5 → 0.05 fraction)
      mde: state.mde / 100,
      alpha: state.alpha,
      power: state.power,
      daily_traffic_estimate: state.dailyTraffic ? parseInt(state.dailyTraffic, 10) : undefined,
    }

    try {
      const res = await fetch('/api/v1/experiments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const json = await res.json()
      if (!res.ok) {
        throw new Error(json?.error?.message ?? `HTTP ${res.status}`)
      }
      const exp = json?.data ?? json
      navigate(`/experiments/${exp.id}`)
    } catch (err) {
      setSubmitError(err.message ?? 'Could not create experiment. Please try again.')
      setSubmitting(false)
    }
  }

  const usersPerGroup = ss ? ss.control_size.toLocaleString() : '—'
  const daysEstimate = rt ? String(rt.days_expected) : '—'
  const daysSub = rt
    ? `95% CI: ${rt.days_lower_95}–${rt.days_upper_95} days`
    : state.dailyTraffic
      ? undefined
      : 'Open Advanced in step 3 to set traffic'

  return (
    <div
      className="p-6 rounded-xl border bg-elevated shadow-elevated"
      style={{ borderColor: 'rgba(59,130,246,0.35)' }}
    >
      <p className="text-xs text-muted uppercase tracking-widest font-medium mb-5">
        Experiment Summary
      </p>

      <div className="grid lg:grid-cols-[1fr_auto] gap-6 mb-6 items-start">
        {/* Left: name + hypothesis + tags */}
        <div className="space-y-2 min-w-0">
          <p className="font-display font-bold text-primary text-lg leading-tight">
            {state.name || 'Untitled Experiment'}
          </p>
          <p className="text-sm text-secondary leading-relaxed line-clamp-3">
            {state.hypothesis || '—'}
          </p>
          <div className="flex items-center gap-2 flex-wrap pt-1">
            {state.industry && (
              <span className="px-2 py-0.5 rounded text-xs border border-subtle text-secondary">
                {state.industry}
              </span>
            )}
            {state.primaryMetricName && (
              <span className="px-2 py-0.5 rounded text-xs border border-subtle text-data font-mono">
                {state.primaryMetricName}
              </span>
            )}
            {state.primaryMetricType && (
              <span className="px-2 py-0.5 rounded text-xs border border-subtle text-secondary capitalize">
                {state.primaryMetricType}
              </span>
            )}
          </div>
        </div>

        {/* Right: 2×2 key numbers grid */}
        <div className="grid grid-cols-2 gap-2 min-w-[260px] flex-shrink-0">
          <KeyNumber label="Users per group" value={usersPerGroup} />
          <KeyNumber label="Estimated days" value={daysEstimate} sub={daysSub} />
          <KeyNumber label="Alpha" value={`α = ${state.alpha}`} />
          <KeyNumber label="Power" value={`${Math.round(state.power * 100)}%`} />
        </div>
      </div>

      <Button size="lg" onClick={handleCreate} loading={submitting} className="w-full">
        Create Experiment
      </Button>

      {submitError && (
        <p
          className="text-xs text-center mt-3 px-3 py-2 rounded-md border"
          style={{
            color: 'var(--color-accent-red)',
            backgroundColor: 'rgba(239,68,68,0.08)',
            borderColor: 'rgba(239,68,68,0.2)',
          }}
        >
          {submitError}
        </p>
      )}

      {!submitError && (
        <p className="text-xs text-muted text-center mt-3">
          Results will be stored and accessible from your experiments dashboard
        </p>
      )}
    </div>
  )
}
