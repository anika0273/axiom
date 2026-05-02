import { useState } from 'react'
import axios from 'axios'

export default function AnalyzePanel() {
  const [form, setForm] = useState({
    test_type: 'proportion',
    control_n: '1000',
    treatment_n: '1000',
    control_success: '100',
    treatment_success: '120',
    control_values: '',
    treatment_values: '',
    alpha: '0.05',
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
      let data
      if (form.test_type === 'proportion') {
        data = {
          control_n: parseInt(form.control_n, 10),
          treatment_n: parseInt(form.treatment_n, 10),
          control_success: parseInt(form.control_success, 10),
          treatment_success: parseInt(form.treatment_success, 10),
        }
      } else {
        const parse = str => str.split(',').map(v => parseFloat(v.trim())).filter(v => !isNaN(v))
        const cv = parse(form.control_values)
        const tv = parse(form.treatment_values)
        if (cv.length === 0 || tv.length === 0) {
          throw new Error('Enter at least one value in each group')
        }
        data = {
          control_n: cv.length,
          treatment_n: tv.length,
          control_success: cv,
          treatment_success: tv,
        }
      }

      const res = await axios.post('/api/v1/stats/analyze', {
        config: { test_type: form.test_type, alpha: parseFloat(form.alpha) },
        data,
      })
      setResult(res.data.data)
    } catch (err) {
      setError(err.response?.data?.error?.message ?? err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
      <h2 className="text-lg font-semibold text-cyan-400 mb-5">Analyze Experiment</h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs text-gray-400 mb-1">Test type</label>
          <select
            value={form.test_type}
            onChange={e => set('test_type', e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/30"
          >
            <option value="proportion">Proportion (conversion rate)</option>
            <option value="mean">Mean (continuous metric)</option>
          </select>
        </div>

        {form.test_type === 'proportion' ? (
          <div className="grid grid-cols-2 gap-3">
            <InputField label="Control users" value={form.control_n} onChange={e => set('control_n', e.target.value)} />
            <InputField label="Control conversions" value={form.control_success} onChange={e => set('control_success', e.target.value)} />
            <InputField label="Treatment users" value={form.treatment_n} onChange={e => set('treatment_n', e.target.value)} />
            <InputField label="Treatment conversions" value={form.treatment_success} onChange={e => set('treatment_success', e.target.value)} />
          </div>
        ) : (
          <div className="space-y-3">
            <Textarea
              label="Control values (comma-separated)"
              placeholder="12.5, 14.2, 9.8, 11.0, …"
              value={form.control_values}
              onChange={e => set('control_values', e.target.value)}
            />
            <Textarea
              label="Treatment values (comma-separated)"
              placeholder="13.1, 15.5, 10.2, 12.7, …"
              value={form.treatment_values}
              onChange={e => set('treatment_values', e.target.value)}
            />
          </div>
        )}

        <InputField label="Alpha (α)" value={form.alpha} onChange={e => set('alpha', e.target.value)} />

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 rounded-lg bg-cyan-700 hover:bg-cyan-600 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors text-sm"
        >
          {loading ? 'Analyzing…' : 'Analyze'}
        </button>
      </form>

      {error && (
        <div className="mt-4 p-3 rounded-lg bg-red-950 border border-red-800 text-red-300 text-sm">
          {error}
        </div>
      )}

      {result && <AnalysisResult result={result} />}
    </div>
  )
}

function AnalysisResult({ result }) {
  const pr = result.primary_result
  const sig = pr.is_significant

  return (
    <div className="mt-5 space-y-3">
      <div className={`rounded-lg p-4 border ${sig ? 'bg-green-950 border-green-700' : 'bg-yellow-950 border-yellow-800'}`}>
        <p className={`text-2xl font-black tracking-wider ${sig ? 'text-green-400' : 'text-yellow-400'}`}>
          {sig ? 'SIGNIFICANT' : 'NOT SIGNIFICANT'}
        </p>
        <p className="text-sm text-gray-400 mt-1">{pr.interpretation}</p>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <MiniCard label="p-value" value={pr.p_value.toFixed(4)} />
        <MiniCard
          label="Relative lift"
          value={`${pr.lift_pct > 0 ? '+' : ''}${pr.lift_pct.toFixed(1)}%`}
        />
        <MiniCard label="Test" value={pr.test_statistic.toFixed(3)} sub={pr.test_type} />
      </div>

      <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
        <p className="text-xs text-gray-500 mb-1">95% Confidence interval (absolute lift)</p>
        <p className="font-mono text-sm text-gray-200">
          [{pr.confidence_interval[0].toFixed(4)},&nbsp;{pr.confidence_interval[1].toFixed(4)}]
        </p>
      </div>

      <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
        <p className="text-xs text-gray-500 mb-1">Plain English</p>
        <p className="text-sm text-gray-200">{result.plain_english}</p>
      </div>

      {result.warnings?.length > 0 && (
        <div className="space-y-1">
          {result.warnings.map((w, i) => (
            <div key={i} className="flex gap-2 items-start p-2 rounded-lg bg-yellow-950 border border-yellow-900 text-xs text-yellow-300">
              <span className="mt-0.5 shrink-0">⚠</span>
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}

      <RecommendationBadge rec={result.overall_recommendation} />
    </div>
  )
}

function RecommendationBadge({ rec }) {
  const styles = {
    STOP_WINNER: 'bg-green-950 border-green-700 text-green-300',
    STOP_NO_EFFECT: 'bg-red-950 border-red-800 text-red-300',
    RUN: 'bg-blue-950 border-blue-800 text-blue-300',
  }
  const cls = styles[rec] ?? 'bg-gray-800 border-gray-700 text-gray-300'
  return (
    <div className={`rounded-lg p-3 border text-sm font-medium ${cls}`}>
      Recommendation: {rec}
    </div>
  )
}

function InputField({ label, value, onChange }) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      <input
        type="number"
        step="any"
        value={value}
        onChange={onChange}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/30"
      />
    </div>
  )
}

function Textarea({ label, value, onChange, placeholder }) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      <textarea
        rows={3}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/30 font-mono"
      />
    </div>
  )
}

function MiniCard({ label, value, sub }) {
  return (
    <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-base font-bold text-white">{value}</p>
      {sub && <p className="text-xs text-gray-600 mt-0.5">{sub}</p>}
    </div>
  )
}
