import { useReducer, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageShell from '../components/layout/PageShell'
import Button from '../components/ui/Button'
import WizardProgress from '../components/wizard/WizardProgress'
import Step1Describe from '../components/wizard/Step1Describe'
import Step2Metrics from '../components/wizard/Step2Metrics'
import Step3Settings from '../components/wizard/Step3Settings'
import SummaryPanel from '../components/wizard/SummaryPanel'
import { useExperimentPlan } from '../hooks/useExperimentPlan'
import { useSampleSize } from '../hooks/useSampleSize'

// ── Form state ────────────────────────────────────────────────────────────────

const initialState = {
  // Step 1
  name: '',
  hypothesis: '',
  industry: '',
  // Step 2
  primaryMetricName: '',
  primaryMetricType: '',
  baseline: '',
  mde: 5,
  secondaryMetrics: [],
  guardrailMetrics: [],
  // Step 3
  alpha: 0.05,
  power: 0.80,
  dailyTraffic: '',
  sequentialTesting: false,
  hasPriorData: false,
  cuped: false,
}

function reducer(state, action) {
  switch (action.type) {
    case 'SET_FIELD':
      return { ...state, [action.field]: action.value }

    case 'FILL_FROM_PLAN': {
      const p = action.plan
      const u = {}

      if (p.experiment_name) u.name = p.experiment_name
      if (p.hypothesis) u.hypothesis = p.hypothesis

      if (p.primary_metric?.name) u.primaryMetricName = p.primary_metric.name
      if (p.primary_metric?.type) u.primaryMetricType = p.primary_metric.type
      if (p.primary_metric?.baseline != null) {
        // API returns 0.03 meaning 3% — convert to "3" for the % input
        u.baseline = String(Math.round(p.primary_metric.baseline * 1000) / 10)
      }

      if (p.recommended_mde != null) {
        // API returns 0.05 meaning 5pp — convert to slider value 5
        u.mde = Math.round(p.recommended_mde * 1000) / 10
        u.mde = Math.min(10, Math.max(0.1, u.mde))
      }

      if (p.secondary_metrics?.length) {
        u.secondaryMetrics = p.secondary_metrics.map((name, i) => ({
          id: `plan-sec-${i}`,
          name,
          type: 'proportion',
        }))
      }

      if (p.guardrail_metrics?.length) {
        u.guardrailMetrics = p.guardrail_metrics.map((name, i) => ({
          id: `plan-grd-${i}`,
          name,
          type: 'proportion',
        }))
      }

      if (p.statistical_config) {
        const sc = p.statistical_config
        if (sc.alpha) u.alpha = sc.alpha
        if (sc.power) u.power = sc.power
        if (sc.sequential_testing) u.sequentialTesting = sc.sequential_testing
        if (sc.cuped_applicable) {
          u.hasPriorData = true
          u.cuped = true
        }
      }

      return { ...state, ...u }
    }

    case 'ADD_METRIC': {
      const key = action.list === 'secondary' ? 'secondaryMetrics' : 'guardrailMetrics'
      return { ...state, [key]: [...state[key], action.metric] }
    }

    case 'REMOVE_METRIC': {
      const key = action.list === 'secondary' ? 'secondaryMetrics' : 'guardrailMetrics'
      return { ...state, [key]: state[key].filter((m) => m.id !== action.id) }
    }

    case 'UPDATE_METRIC': {
      const key = action.list === 'secondary' ? 'secondaryMetrics' : 'guardrailMetrics'
      return {
        ...state,
        [key]: state[key].map((m) =>
          m.id === action.id ? { ...m, [action.field]: action.value } : m,
        ),
      }
    }

    default:
      return state
  }
}

// ── Validation ────────────────────────────────────────────────────────────────

function step1Valid(s) {
  return s.name.trim().length >= 3 && s.hypothesis.trim().length >= 10 && s.industry !== ''
}

function step2Valid(s) {
  return (
    s.primaryMetricName.trim().length > 0 &&
    s.primaryMetricType !== '' &&
    s.baseline !== '' &&
    parseFloat(s.baseline) > 0
  )
}

function step3Valid() {
  return true // alpha and power always have defaults
}

const validators = [step1Valid, step2Valid, step3Valid]

// ── Component ─────────────────────────────────────────────────────────────────

export default function NewExperiment() {
  const [step, setStep] = useState(1)
  const [showErrors, setShowErrors] = useState(false)
  const navigate = useNavigate()

  const [state, dispatch] = useReducer(reducer, initialState)
  const planHook = useExperimentPlan()
  const { result: sampleSizeResult, loading: sampleSizeLoading, stale: sampleSizeStale } =
    useSampleSize({
      baseline: state.baseline,
      mde: state.mde,
      alpha: state.alpha,
      power: state.power,
      dailyTraffic: state.dailyTraffic,
    })

  const isSummary = step === 4
  const currentValid = isSummary ? true : validators[step - 1](state)

  function handleNext() {
    if (!currentValid) {
      setShowErrors(true)
      return
    }
    setShowErrors(false)
    setStep((s) => s + 1)
  }

  function handleBack() {
    setShowErrors(false)
    if (step > 1) setStep((s) => s - 1)
    else navigate('/experiments')
  }

  function handleGoTo(targetStep) {
    setShowErrors(false)
    setStep(targetStep)
  }

  return (
    <PageShell
      breadcrumbs={[
        { label: 'Experiments', href: '/experiments' },
        { label: 'New Experiment' },
      ]}
    >
      {/* Subtle radial gradient overlay */}
      <div
        className="min-h-screen"
        style={{
          background:
            'radial-gradient(ellipse 80% 50% at 50% 20%, rgba(59,130,246,0.05) 0%, transparent 70%)',
        }}
      >
        <div className="max-w-4xl mx-auto">
          {/* Page header */}
          <div className="mb-8">
            <h1 className="font-display text-3xl font-bold text-primary mb-2">
              New Experiment
            </h1>
            <p className="text-secondary">
              Define your hypothesis, metrics, and statistical settings.
            </p>
          </div>

          {/* Step progress indicator (steps 1-3 only) */}
          {!isSummary && (
            <div className="mb-8">
              <WizardProgress currentStep={step} onGoTo={handleGoTo} />
            </div>
          )}

          {/* Step content — key prop triggers slide-in on every step change */}
          <div key={step} className="step-slide-in">
            {step === 1 && (
              <Step1Describe
                state={state}
                dispatch={dispatch}
                planHook={planHook}
                showErrors={showErrors}
              />
            )}

            {step === 2 && (
              <Step2Metrics
                state={state}
                dispatch={dispatch}
                sampleSizeResult={sampleSizeResult}
                sampleSizeLoading={sampleSizeLoading}
                sampleSizeStale={sampleSizeStale}
                showErrors={showErrors}
              />
            )}

            {step === 3 && (
              <Step3Settings
                state={state}
                dispatch={dispatch}
                showErrors={showErrors}
              />
            )}

            {isSummary && (
              <SummaryPanel state={state} sampleSizeResult={sampleSizeResult} />
            )}
          </div>

          {/* Navigation */}
          <div className="flex items-center justify-between mt-8 pb-12">
            <Button variant="ghost" onClick={handleBack}>
              {step > 1 ? '← Back' : 'Cancel'}
            </Button>

            {!isSummary && (
              <Button onClick={handleNext} disabled={planHook.loading}>
                {step < 3 ? 'Continue →' : 'Review Experiment →'}
              </Button>
            )}
          </div>
        </div>
      </div>
    </PageShell>
  )
}
