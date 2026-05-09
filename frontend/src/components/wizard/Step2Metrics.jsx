import { useState } from 'react'
import { Plus, X, Info } from 'lucide-react'
import LoadingSpinner from '../ui/LoadingSpinner'

const METRIC_SUGGESTIONS = [
  'conversion_rate',
  'revenue_per_user',
  'session_duration',
  'click_through_rate',
  'trial_to_paid',
  'gmv_per_seller',
]

const METRIC_TYPES = [
  {
    id: 'proportion',
    label: 'Proportion',
    icon: '%',
    description: 'Binary outcomes (conversions, clicks)',
  },
  {
    id: 'mean',
    label: 'Mean',
    icon: 'μ',
    description: 'Continuous values (revenue, duration)',
  },
  {
    id: 'ratio',
    label: 'Ratio',
    icon: '/',
    description: 'Rates and ratios (items per order)',
  },
]

function runtimeColor(days) {
  if (days < 14) return 'text-green'
  if (days <= 30) return 'text-amber'
  return 'text-red'
}

/**
 * Step 2 — "Configure your metrics"
 * Primary metric (name autocomplete, type cards, baseline, MDE slider),
 * secondary metrics list, guardrail metrics list.
 * sampleSizeResult/loading/stale are passed down from NewExperiment.
 */
export default function Step2Metrics({
  state,
  dispatch,
  sampleSizeResult,
  sampleSizeLoading,
  sampleSizeStale,
  showErrors,
}) {
  const [showSuggestions, setShowSuggestions] = useState(false)
  const filtered = METRIC_SUGGESTIONS.filter((s) =>
    s.includes(state.primaryMetricName.toLowerCase()),
  )

  const ss = sampleSizeResult?.ss
  const rt = sampleSizeResult?.runtime

  function addMetric(list) {
    const id = `${list}-${Date.now()}`
    dispatch({ type: 'ADD_METRIC', list, metric: { id, name: '', type: 'proportion' } })
  }

  function removeMetric(list, id) {
    dispatch({ type: 'REMOVE_METRIC', list, id })
  }

  function updateMetric(list, id, field, value) {
    dispatch({ type: 'UPDATE_METRIC', list, id, field, value })
  }

  return (
    <div className="space-y-10">
      {/* ── Primary metric ── */}
      <section>
        <p className="text-xs text-muted uppercase tracking-widest font-medium mb-5">
          Primary Metric
        </p>

        <div className="space-y-5">
          {/* Metric name with autocomplete */}
          <div className="relative">
            <label className="block text-xs text-secondary uppercase tracking-widest mb-2">
              Metric Name
            </label>
            <input
              type="text"
              value={state.primaryMetricName}
              onChange={(e) => {
                dispatch({
                  type: 'SET_FIELD',
                  field: 'primaryMetricName',
                  value: e.target.value,
                })
                setShowSuggestions(true)
              }}
              onFocus={() => setShowSuggestions(true)}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
              placeholder="e.g. conversion_rate"
              className="w-full bg-elevated border border-subtle rounded-md px-3 py-2.5 text-sm text-primary font-mono placeholder:text-muted placeholder:font-sans focus:outline-none focus:border-active transition-colors"
            />
            {showErrors && !state.primaryMetricName.trim() && (
              <p className="text-xs text-red mt-1">Primary metric name is required</p>
            )}

            {/* Autocomplete dropdown */}
            {showSuggestions && filtered.length > 0 && (
              <div className="absolute z-20 top-full mt-1 w-full bg-elevated border border-subtle rounded-md shadow-elevated overflow-hidden">
                {filtered.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onMouseDown={() => {
                      dispatch({ type: 'SET_FIELD', field: 'primaryMetricName', value: s })
                      setShowSuggestions(false)
                    }}
                    className="w-full text-left px-3 py-2 text-sm text-secondary hover:bg-hover hover:text-primary transition-colors font-mono"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Metric type cards */}
          <div>
            <label className="block text-xs text-secondary uppercase tracking-widest mb-2">
              Metric Type
            </label>
            <div className="grid grid-cols-3 gap-3">
              {METRIC_TYPES.map((type) => {
                const selected = state.primaryMetricType === type.id
                return (
                  <button
                    key={type.id}
                    type="button"
                    onClick={() =>
                      dispatch({
                        type: 'SET_FIELD',
                        field: 'primaryMetricType',
                        value: type.id,
                      })
                    }
                    className={[
                      'p-4 rounded-lg border text-left transition-all',
                      selected
                        ? 'border-blue shadow-glow'
                        : 'border-subtle bg-elevated hover:border-active hover:bg-hover',
                    ].join(' ')}
                    style={
                      selected ? { backgroundColor: 'rgba(59,130,246,0.08)' } : undefined
                    }
                  >
                    <span className="text-xl font-mono text-data block mb-1.5">
                      {type.icon}
                    </span>
                    <span className="text-sm font-semibold text-primary block mb-0.5">
                      {type.label}
                    </span>
                    <span className="text-xs text-secondary leading-snug">
                      {type.description}
                    </span>
                  </button>
                )
              })}
            </div>
            {showErrors && !state.primaryMetricType && (
              <p className="text-xs text-red mt-1">Please select a metric type</p>
            )}
          </div>

          {/* Baseline + MDE slider */}
          <div className="grid sm:grid-cols-2 gap-5">
            <div>
              <label className="block text-xs text-secondary uppercase tracking-widest mb-2">
                Baseline Value{state.primaryMetricType === 'proportion' ? ' (%)' : ''}
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={state.baseline}
                  onChange={(e) =>
                    dispatch({ type: 'SET_FIELD', field: 'baseline', value: e.target.value })
                  }
                  placeholder={state.primaryMetricType === 'proportion' ? '3.0' : '0.00'}
                  className="flex-1 bg-elevated border border-subtle rounded-md px-3 py-2.5 text-sm text-primary placeholder:text-muted focus:outline-none focus:border-active transition-colors"
                />
                {state.primaryMetricType === 'proportion' && (
                  <span className="text-sm text-muted font-medium">%</span>
                )}
              </div>
              {showErrors && (!state.baseline || parseFloat(state.baseline) <= 0) && (
                <p className="text-xs text-red mt-1">Baseline value is required</p>
              )}
            </div>

            <div>
              <label className="block text-xs text-secondary uppercase tracking-widest mb-2">
                Min Detectable Effect
              </label>
              <div className="flex items-center gap-3 mt-1">
                <input
                  type="range"
                  min="0.1"
                  max="10"
                  step="0.1"
                  value={state.mde}
                  onChange={(e) =>
                    dispatch({
                      type: 'SET_FIELD',
                      field: 'mde',
                      value: parseFloat(e.target.value),
                    })
                  }
                  className="flex-1 accent-blue cursor-pointer"
                />
                <span className="text-sm font-mono text-data w-12 text-right flex-shrink-0">
                  {state.mde.toFixed(1)}%
                </span>
              </div>
              <p className="text-xs text-muted mt-1">Absolute lift in percentage points</p>
            </div>
          </div>

          {/* Live sample size display */}
          <SampleSizeDisplay
            ss={ss}
            rt={rt}
            mde={state.mde}
            loading={sampleSizeLoading}
            stale={sampleSizeStale}
            metricType={state.primaryMetricType}
            baseline={state.baseline}
            dailyTraffic={state.dailyTraffic}
          />
        </div>
      </section>

      {/* ── Secondary metrics ── */}
      <MetricList
        title="Secondary Metrics"
        list={state.secondaryMetrics}
        onAdd={() => addMetric('secondary')}
        onRemove={(id) => removeMetric('secondary', id)}
        onUpdate={(id, f, v) => updateMetric('secondary', id, f, v)}
        maxItems={5}
      />

      {/* ── Guardrail metrics ── */}
      <MetricList
        title="Guardrail Metrics"
        list={state.guardrailMetrics}
        onAdd={() => addMetric('guardrail')}
        onRemove={(id) => removeMetric('guardrail', id)}
        onUpdate={(id, f, v) => updateMetric('guardrail', id, f, v)}
        maxItems={5}
        tooltip="Guardrail metrics must not degrade significantly — they're your safety checks"
      />
    </div>
  )
}

// ── Sample size live display ────────────────────────────────────────────────

function SampleSizeDisplay({ ss, rt, mde, loading, stale, metricType, baseline, dailyTraffic }) {
  const canCalculate =
    metricType === 'proportion' &&
    baseline &&
    parseFloat(baseline) > 0 &&
    parseFloat(baseline) < 100

  return (
    <div
      className={[
        'p-4 rounded-lg border border-subtle bg-elevated transition-opacity duration-200 min-h-[64px] flex items-start',
        stale && !loading ? 'opacity-50' : 'opacity-100',
      ].join(' ')}
    >
      {loading && (
        <div className="flex items-center gap-2 text-sm text-secondary">
          <LoadingSpinner size={14} />
          <span>Calculating sample size...</span>
        </div>
      )}

      {!loading && ss && (
        <div className="w-full">
          <p
            className={[
              'text-sm font-medium leading-relaxed',
              rt ? runtimeColor(rt.days_expected) : 'text-primary',
            ].join(' ')}
          >
            To detect a{' '}
            <span className="font-mono">{mde.toFixed(1)}pp</span> improvement you need{' '}
            <span className="font-mono">{ss.control_size.toLocaleString()}</span> users per
            group
            {rt && (
              <>
                {' '}— estimated{' '}
                <span className="font-mono">{rt.days_expected}</span> days at your traffic
                volume
              </>
            )}
          </p>
          {rt && (
            <p className="text-xs text-muted mt-1">
              95% CI: {rt.days_lower_95}–{rt.days_upper_95} days
            </p>
          )}
          {!rt && dailyTraffic === '' && (
            <p className="text-xs text-muted mt-1">
              Set daily traffic in step 3 to see runtime estimate
            </p>
          )}
        </div>
      )}

      {!loading && !ss && !canCalculate && metricType && (
        <p className="text-sm text-muted">
          {metricType !== 'proportion'
            ? 'Sample size calculation is available for proportion metrics only.'
            : 'Enter a baseline value between 0% and 100% to see sample size.'}
        </p>
      )}

      {!loading && !ss && !metricType && (
        <p className="text-sm text-muted">Select a metric type and baseline to see sample size.</p>
      )}
    </div>
  )
}

// ── Reusable metric list (secondary / guardrail) ────────────────────────────

function MetricList({ title, list, onAdd, onRemove, onUpdate, maxItems, tooltip }) {
  return (
    <section>
      <div className="flex items-center gap-2 mb-3">
        <p className="text-xs text-muted uppercase tracking-widest font-medium">{title}</p>
        {tooltip && (
          <span title={tooltip} className="text-muted cursor-help flex-shrink-0">
            <Info size={12} />
          </span>
        )}
      </div>

      {list.length > 0 && (
        <div className="space-y-2 mb-3">
          {list.map((m) => (
            <div key={m.id} className="flex items-center gap-2">
              <input
                type="text"
                value={m.name}
                onChange={(e) => onUpdate(m.id, 'name', e.target.value)}
                placeholder="metric_name"
                className="flex-1 bg-elevated border border-subtle rounded-md px-3 py-2 text-sm text-primary font-mono placeholder:text-muted placeholder:font-sans focus:outline-none focus:border-active transition-colors"
              />
              <select
                value={m.type}
                onChange={(e) => onUpdate(m.id, 'type', e.target.value)}
                className="bg-elevated border border-subtle rounded-md px-2 py-2 text-sm text-secondary focus:outline-none focus:border-active transition-colors"
              >
                <option value="proportion">Proportion</option>
                <option value="mean">Mean</option>
                <option value="ratio">Ratio</option>
              </select>
              <button
                type="button"
                onClick={() => onRemove(m.id)}
                className="p-1.5 text-muted hover:text-red transition-colors rounded"
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {list.length < maxItems && (
        <button
          type="button"
          onClick={onAdd}
          className="flex items-center gap-1.5 text-xs text-secondary hover:text-primary transition-colors"
        >
          <Plus size={13} />
          Add {title.split(' ')[0].toLowerCase()} metric
        </button>
      )}
    </section>
  )
}
