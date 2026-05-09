import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

const ALPHA_OPTIONS = [
  {
    value: 0.01,
    label: 'α = 0.01',
    detail: '1 in 100 false positive rate',
    sub: 'Safety-critical tests',
  },
  {
    value: 0.05,
    label: 'α = 0.05',
    detail: '1 in 20 false positive rate',
    sub: 'Standard industry default',
  },
  {
    value: 0.10,
    label: 'α = 0.10',
    detail: '1 in 10 false positive rate',
    sub: 'Exploratory tests',
  },
]

const POWER_OPTIONS = [
  {
    value: 0.80,
    label: '80% power',
    detail: 'Catches 80% of real effects',
    sub: 'Smallest sample size',
  },
  {
    value: 0.90,
    label: '90% power',
    detail: 'Catches 90% of real effects',
    sub: '+25% sample size vs 80%',
  },
  {
    value: 0.95,
    label: '95% power',
    detail: 'Catches 95% of real effects',
    sub: '+60% sample size vs 80%',
  },
]

function OptionCard({ label, detail, sub, selected, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'p-4 rounded-lg border text-left transition-all w-full',
        selected
          ? 'border-blue shadow-glow'
          : 'border-subtle bg-elevated hover:border-active hover:bg-hover',
      ].join(' ')}
      style={selected ? { backgroundColor: 'rgba(59,130,246,0.08)' } : undefined}
    >
      <span className="text-sm font-bold text-primary block mb-1">{label}</span>
      <span className="text-xs text-secondary block">{detail}</span>
      {sub && <span className="text-xs text-muted block mt-1">{sub}</span>}
    </button>
  )
}

function Toggle({ checked, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={[
        'relative w-9 h-5 rounded-full transition-colors duration-200 flex-shrink-0 focus:outline-none focus:ring-2 focus:ring-blue focus:ring-offset-1 focus:ring-offset-deep',
        checked ? 'bg-blue' : 'bg-subtle',
      ].join(' ')}
    >
      <span
        className={[
          'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200',
          checked ? 'translate-x-4' : 'translate-x-0.5',
        ].join(' ')}
      />
    </button>
  )
}

/**
 * Step 3 — "Statistical configuration"
 * Alpha cards, power cards, collapsed advanced section (daily traffic, sequential, CUPED).
 */
export default function Step3Settings({ state, dispatch, showErrors }) {
  const [advancedOpen, setAdvancedOpen] = useState(false)

  function set(field, value) {
    dispatch({ type: 'SET_FIELD', field, value })
  }

  return (
    <div className="space-y-8 max-w-2xl">
      {/* ── Significance level ── */}
      <section>
        <p className="text-xs text-muted uppercase tracking-widest font-medium mb-4">
          Significance Level (Alpha)
        </p>
        <div className="grid grid-cols-3 gap-3">
          {ALPHA_OPTIONS.map((opt) => (
            <OptionCard
              key={opt.value}
              label={opt.label}
              detail={opt.detail}
              sub={opt.sub}
              selected={state.alpha === opt.value}
              onClick={() => set('alpha', opt.value)}
            />
          ))}
        </div>
      </section>

      {/* ── Statistical power ── */}
      <section>
        <p className="text-xs text-muted uppercase tracking-widest font-medium mb-4">
          Statistical Power
        </p>
        <div className="grid grid-cols-3 gap-3">
          {POWER_OPTIONS.map((opt) => (
            <OptionCard
              key={opt.value}
              label={opt.label}
              detail={opt.detail}
              sub={opt.sub}
              selected={state.power === opt.value}
              onClick={() => set('power', opt.value)}
            />
          ))}
        </div>
      </section>

      {/* ── Advanced settings (collapsed) ── */}
      <section>
        <button
          type="button"
          onClick={() => setAdvancedOpen((o) => !o)}
          className="flex items-center gap-2 text-xs text-secondary hover:text-primary transition-colors focus:outline-none"
        >
          {advancedOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
          <span className="uppercase tracking-widest font-medium">Advanced Settings</span>
        </button>

        {advancedOpen && (
          <div className="mt-5 pl-5 border-l border-subtle space-y-6">
            {/* Daily traffic */}
            <div>
              <label className="block text-xs text-secondary uppercase tracking-widest mb-2">
                Daily Traffic (users / day)
              </label>
              <input
                type="number"
                min="1"
                value={state.dailyTraffic}
                onChange={(e) => set('dailyTraffic', e.target.value)}
                placeholder="e.g. 500"
                className="w-48 bg-elevated border border-subtle rounded-md px-3 py-2.5 text-sm text-primary placeholder:text-muted focus:outline-none focus:border-active transition-colors"
              />
              <p className="text-xs text-muted mt-1">Used to estimate experiment runtime</p>
            </div>

            {/* Sequential testing toggle */}
            <label className="flex items-start gap-3 cursor-pointer">
              <Toggle
                checked={state.sequentialTesting}
                onChange={(v) => set('sequentialTesting', v)}
              />
              <div className="pt-0.5">
                <span className="text-sm text-primary block mb-0.5">Sequential Testing</span>
                <span className="text-xs text-muted leading-snug block">
                  Allows valid early stopping without inflating the false positive rate. Best
                  for long-running experiments.
                </span>
              </div>
            </label>

            {/* Pre-experiment data checkbox */}
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={state.hasPriorData}
                onChange={(e) => {
                  set('hasPriorData', e.target.checked)
                  if (!e.target.checked) set('cuped', false)
                }}
                className="w-4 h-4 rounded accent-blue cursor-pointer"
              />
              <span className="text-sm text-secondary">I have pre-experiment data</span>
            </label>

            {/* CUPED (only visible if hasPriorData) */}
            {state.hasPriorData && (
              <label className="flex items-center gap-3 cursor-pointer pl-7">
                <input
                  type="checkbox"
                  checked={state.cuped}
                  onChange={(e) => set('cuped', e.target.checked)}
                  className="w-4 h-4 rounded accent-blue cursor-pointer"
                />
                <div>
                  <span className="text-sm text-secondary block">
                    Enable CUPED variance reduction
                  </span>
                  <span className="text-xs text-muted">
                    Uses pre-experiment covariate to reduce required sample size
                  </span>
                </div>
              </label>
            )}
          </div>
        )}
      </section>
    </div>
  )
}
