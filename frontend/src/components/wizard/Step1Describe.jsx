import { useEffect, useState } from 'react'
import AIPlanPanel from './AIPlanPanel'

const INDUSTRIES = [
  'E-commerce',
  'SaaS',
  'Marketplace',
  'Media',
  'Fintech',
  'Healthcare',
  'Other',
]

/**
 * Step 1 — "What are you testing?"
 * Two-column layout: left = manual form, right = AI planning panel.
 * When the AI plan fills in, name/hypothesis fields briefly highlight in blue.
 */
export default function Step1Describe({ state, dispatch, planHook, showErrors }) {
  const { plan, loading, error, questions, planExperiment } = planHook
  const [highlighted, setHighlighted] = useState([])

  // Flash blue highlight on fields that were just filled by the AI plan
  useEffect(() => {
    if (!plan) return
    const filled = []
    if (plan.experiment_name) filled.push('name')
    if (plan.hypothesis) filled.push('hypothesis')
    setHighlighted(filled)
    const t = setTimeout(() => setHighlighted([]), 1300)
    return () => clearTimeout(t)
  }, [plan])

  async function handlePlan(description) {
    const result = await planExperiment(description)
    if (result?.plan) {
      dispatch({ type: 'FILL_FROM_PLAN', plan: result.plan })
    }
  }

  function inputClass(fieldName) {
    return [
      'w-full bg-elevated border rounded-md px-3 py-2.5 text-sm text-primary',
      'placeholder:text-muted focus:outline-none transition-colors',
      highlighted.includes(fieldName) ? 'field-highlight' : 'border-subtle focus:border-active',
    ].join(' ')
  }

  return (
    <div className="grid lg:grid-cols-[3fr_2fr] gap-6 items-start">
      {/* ── Left: manual form ── */}
      <div className="space-y-5">
        <p className="text-xs text-muted uppercase tracking-widest font-medium">
          Experiment Brief
        </p>

        {/* Name */}
        <div>
          <label className="block text-xs text-secondary uppercase tracking-widest mb-2">
            Experiment Name
          </label>
          <input
            type="text"
            value={state.name}
            onChange={(e) =>
              dispatch({ type: 'SET_FIELD', field: 'name', value: e.target.value })
            }
            placeholder="e.g. Checkout Button Color Test"
            className={inputClass('name')}
          />
          {showErrors && state.name.trim().length < 3 && (
            <p className="text-xs text-red mt-1">
              Experiment name is required (at least 3 characters)
            </p>
          )}
        </div>

        {/* Hypothesis */}
        <div>
          <label className="block text-xs text-secondary uppercase tracking-widest mb-2">
            Hypothesis
          </label>
          <textarea
            rows={4}
            value={state.hypothesis}
            onChange={(e) =>
              dispatch({ type: 'SET_FIELD', field: 'hypothesis', value: e.target.value })
            }
            placeholder={'We believe that [change] will cause [effect]\nbecause [reasoning].'}
            className={[inputClass('hypothesis'), 'resize-none'].join(' ')}
          />
          {showErrors && state.hypothesis.trim().length < 10 && (
            <p className="text-xs text-red mt-1">
              Hypothesis is required (at least 10 characters)
            </p>
          )}
        </div>

        {/* Industry */}
        <div>
          <label className="block text-xs text-secondary uppercase tracking-widest mb-2">
            Industry
          </label>
          <select
            value={state.industry}
            onChange={(e) =>
              dispatch({ type: 'SET_FIELD', field: 'industry', value: e.target.value })
            }
            className={[
              'w-full bg-elevated border border-subtle rounded-md px-3 py-2.5 text-sm',
              'focus:outline-none focus:border-active transition-colors appearance-none cursor-pointer',
              state.industry ? 'text-primary' : 'text-muted',
            ].join(' ')}
          >
            <option value="" disabled>
              Select an industry
            </option>
            {INDUSTRIES.map((ind) => (
              <option key={ind} value={ind}>
                {ind}
              </option>
            ))}
          </select>
          {showErrors && !state.industry && (
            <p className="text-xs text-red mt-1">Please select an industry</p>
          )}
        </div>
      </div>

      {/* ── Right: AI panel ── */}
      <AIPlanPanel
        onPlan={handlePlan}
        loading={loading}
        error={error}
        questions={questions}
        plan={plan}
      />
    </div>
  )
}
