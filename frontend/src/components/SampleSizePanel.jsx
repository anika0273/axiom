import { useState } from 'react'
import axios from 'axios'

const COHENS_TIERS = [
  { min: 0.8, label: 'Large', color: 'text-green-400' },
  { min: 0.5, label: 'Medium', color: 'text-yellow-400' },
  { min: 0.2, label: 'Small', color: 'text-orange-400' },
  { min: 0, label: 'Tiny', color: 'text-red-400' },
]

function cohensLabel(d) {
  const abs = Math.abs(d)
  for (const t of COHENS_TIERS) {
    if (abs >= t.min) return t
  }
  return COHENS_TIERS[COHENS_TIERS.length - 1]
}

export default function SampleSizePanel() {
  const [form, setForm] = useState({
    baseline_rate: '0.10',
    mde: '0.02',
    alpha: '0.05',
    power: '0.80',
    daily_traffic: '',
  })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  function set(name, value) {
    setForm(f => ({ ...f, [name]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const ssRes = await axios.post('/api/v1/stats/power/sample-size', {
        baseline_rate: parseFloat(form.baseline_rate),
        mde: parseFloat(form.mde),
        alpha: parseFloat(form.alpha),
        power: parseFloat(form.power),
      })
      const ss = ssRes.data.data

      let runtime = null
      if (form.daily_traffic) {
        const rtRes = await axios.post('/api/v1/stats/power/runtime', {
          required_sample_size: ss.total_sample_size,
          daily_traffic: parseInt(form.daily_traffic, 10),
        })
        runtime = rtRes.data.data
      }

      setResult({ ss, runtime })
    } catch (err) {
      setError(err.response?.data?.error?.message ?? err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
      <h2 className="text-lg font-semibold text-cyan-400 mb-5">Sample Size Calculator</h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Field
            label="Baseline rate"
            hint="e.g. 0.10 = 10% CVR"
            name="baseline_rate"
            value={form.baseline_rate}
            onChange={e => set('baseline_rate', e.target.value)}
            placeholder="0.10"
          />
          <Field
            label="MDE (absolute)"
            hint="Minimum detectable effect"
            name="mde"
            value={form.mde}
            onChange={e => set('mde', e.target.value)}
            placeholder="0.02"
          />
          <Field
            label="Alpha (α)"
            name="alpha"
            value={form.alpha}
            onChange={e => set('alpha', e.target.value)}
            placeholder="0.05"
          />
          <Field
            label="Power (1−β)"
            name="power"
            value={form.power}
            onChange={e => set('power', e.target.value)}
            placeholder="0.80"
          />
        </div>

        <Field
          label="Daily traffic (optional)"
          hint="Leave blank to skip runtime estimate"
          name="daily_traffic"
          value={form.daily_traffic}
          onChange={e => set('daily_traffic', e.target.value)}
          placeholder="e.g. 500"
        />

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 rounded-lg bg-cyan-700 hover:bg-cyan-600 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors text-sm"
        >
          {loading ? 'Calculating…' : 'Calculate'}
        </button>
      </form>

      {error && <ErrorBanner message={error} />}

      {result && <Results result={result} />}
    </div>
  )
}

function Results({ result }) {
  const { ss, runtime } = result
  const tier = cohensLabel(ss.cohens_d)

  return (
    <div className="mt-5 grid grid-cols-2 gap-3">
      <StatCard label="Users per group" value={ss.control_size.toLocaleString()} />
      <StatCard label="Total users needed" value={ss.total_sample_size.toLocaleString()} />

      {runtime ? (
        <>
          <StatCard
            label="Est. runtime"
            value={`${runtime.days_expected} days`}
            sub={`${runtime.weeks_expected}w · 95% CI: ${runtime.days_lower_95}–${runtime.days_upper_95}d`}
          />
          <StatCard
            label="Cohen's d"
            value={ss.cohens_d.toFixed(4)}
            sub={<span className={tier.color}>{tier.label} effect</span>}
          />
        </>
      ) : (
        <StatCard
          label="Cohen's d"
          value={ss.cohens_d.toFixed(4)}
          sub={<span className={tier.color}>{tier.label} effect</span>}
          wide
        />
      )}
    </div>
  )
}

function Field({ label, name, value, onChange, placeholder, hint }) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-0.5">{label}</label>
      {hint && <p className="text-xs text-gray-600 mb-1">{hint}</p>}
      <input
        type="number"
        step="any"
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/30"
      />
    </div>
  )
}

function StatCard({ label, value, sub, wide }) {
  return (
    <div className={`bg-gray-800 rounded-lg p-4 border border-gray-700 ${wide ? 'col-span-2' : ''}`}>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-xl font-bold text-white">{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  )
}

function ErrorBanner({ message }) {
  return (
    <div className="mt-4 p-3 rounded-lg bg-red-950 border border-red-800 text-red-300 text-sm">
      {message}
    </div>
  )
}
