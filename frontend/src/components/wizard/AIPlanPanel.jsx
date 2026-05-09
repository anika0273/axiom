import { useState, useEffect, useRef } from 'react'
import { Sparkles, Check, AlertTriangle, HelpCircle } from 'lucide-react'
import Button from '../ui/Button'

const LOADING_MESSAGES = [
  'Identifying metric type...',
  'Calculating sample size...',
  'Assessing risks...',
  'Structuring your plan...',
]

/**
 * Right-column AI planning panel in Step 1.
 * onPlan(description) — called when user clicks "Plan with AI".
 * loading/error/questions/plan — state from useExperimentPlan.
 */
export default function AIPlanPanel({ onPlan, loading, error, questions, plan }) {
  const [description, setDescription] = useState('')
  const [msgIdx, setMsgIdx] = useState(0)
  const intervalRef = useRef(null)

  useEffect(() => {
    if (loading) {
      setMsgIdx(0)
      intervalRef.current = setInterval(() => {
        setMsgIdx((i) => (i + 1) % LOADING_MESSAGES.length)
      }, 1600)
    } else {
      clearInterval(intervalRef.current)
    }
    return () => clearInterval(intervalRef.current)
  }, [loading])

  const hasPlan = !!plan
  const hasQuestions = questions.length > 0

  return (
    <div
      className="flex flex-col gap-4 p-5 rounded-xl border bg-elevated shadow-elevated h-full"
      style={{ borderColor: 'rgba(59,130,246,0.3)' }}
    >
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Sparkles size={14} className="text-blue flex-shrink-0" />
          <span className="text-sm font-semibold text-primary">Let Axiom Plan This</span>
        </div>
        <p className="text-xs text-secondary leading-relaxed">
          Describe your experiment in plain English and Axiom will configure everything automatically.
        </p>
      </div>

      {/* Textarea */}
      <textarea
        rows={6}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder={
          'e.g. We want to test if changing our checkout button from green to orange increases purchases. We get about 500 orders per day and our current conversion rate is about 3%.'
        }
        disabled={loading}
        className="w-full flex-1 bg-card border border-subtle rounded-md px-3 py-2.5 text-sm text-primary placeholder:text-muted focus:outline-none focus:border-active transition-colors resize-none disabled:opacity-60"
      />

      {/* CTA button */}
      <Button
        variant="primary"
        size="md"
        loading={loading}
        disabled={!description.trim() || loading}
        onClick={() => onPlan(description)}
        className="w-full"
      >
        {loading ? 'Analyzing...' : hasPlan ? 'Re-plan with AI →' : 'Plan with AI →'}
      </Button>

      {/* Cycling status message while loading */}
      {loading && (
        <p className="text-xs text-secondary text-center animate-pulse">
          {LOADING_MESSAGES[msgIdx]}
        </p>
      )}

      {/* Success state */}
      {hasPlan && !loading && (
        <div
          className="flex items-center gap-2 px-3 py-2 rounded-md border"
          style={{
            backgroundColor: 'rgba(16,185,129,0.08)',
            borderColor: 'rgba(16,185,129,0.25)',
          }}
        >
          <Check size={13} className="text-green flex-shrink-0" />
          <span className="text-xs text-green font-medium">Plan ready — form filled</span>
        </div>
      )}

      {/* Error state with optional clarifying questions */}
      {error && !loading && (
        <div
          className="px-3 py-2.5 rounded-md border"
          style={{
            backgroundColor: 'rgba(245,158,11,0.08)',
            borderColor: 'rgba(245,158,11,0.25)',
          }}
        >
          <div className="flex items-start gap-2 mb-2">
            <AlertTriangle size={13} className="text-amber flex-shrink-0 mt-0.5" />
            <p className="text-xs text-amber leading-relaxed">{error}</p>
          </div>
          {hasQuestions && <ClarifyingQuestions questions={questions} />}
        </div>
      )}

      {/* Clarifying questions (needs_clarification path, no error) */}
      {!error && hasQuestions && !hasPlan && !loading && (
        <div
          className="px-3 py-2.5 rounded-md border"
          style={{
            backgroundColor: 'rgba(245,158,11,0.08)',
            borderColor: 'rgba(245,158,11,0.25)',
          }}
        >
          <p className="text-xs text-amber font-medium mb-2">Need more details to plan:</p>
          <ClarifyingQuestions questions={questions} />
        </div>
      )}
    </div>
  )
}

function ClarifyingQuestions({ questions }) {
  return (
    <div className="space-y-1.5">
      {questions.map((q, i) => (
        <div key={i} className="flex items-start gap-1.5">
          <HelpCircle size={11} className="text-muted flex-shrink-0 mt-0.5" />
          <p className="text-xs text-secondary leading-snug">{q}</p>
        </div>
      ))}
    </div>
  )
}
