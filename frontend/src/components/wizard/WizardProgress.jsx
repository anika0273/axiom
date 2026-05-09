import { Check } from 'lucide-react'

const STEPS = [
  { id: 1, label: 'Describe' },
  { id: 2, label: 'Metrics' },
  { id: 3, label: 'Statistics' },
]

/**
 * Three-step progress indicator. Completed steps show a green checkmark and
 * are clickable (to go back). Active step has a blue filled circle.
 */
export default function WizardProgress({ currentStep, onGoTo }) {
  return (
    <div className="flex items-center w-full">
      {STEPS.map((step, i) => {
        const isDone = step.id < currentStep
        const isActive = step.id === currentStep

        return (
          <div key={step.id} className="flex items-center flex-1 last:flex-none">
            <button
              type="button"
              onClick={() => isDone && onGoTo(step.id)}
              disabled={!isDone}
              className="flex items-center gap-2.5 group focus:outline-none"
            >
              {/* Circle */}
              <div
                className={[
                  'w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold',
                  'transition-all duration-200 flex-shrink-0',
                  isDone && 'bg-green text-deep cursor-pointer group-hover:brightness-110',
                  isActive && 'bg-blue text-white shadow-glow',
                  !isDone && !isActive && 'border-2 border-subtle text-muted',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                {isDone ? <Check size={13} strokeWidth={3} /> : step.id}
              </div>

              {/* Label */}
              <span
                className={[
                  'text-sm font-medium hidden sm:block transition-colors',
                  isDone && 'text-secondary cursor-pointer group-hover:text-primary',
                  isActive && 'text-primary',
                  !isDone && !isActive && 'text-muted',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                {step.label}
              </span>
            </button>

            {/* Connector line */}
            {i < STEPS.length - 1 && (
              <div
                className={[
                  'flex-1 h-px mx-4 transition-all duration-300',
                  isDone ? 'bg-green opacity-40' : 'bg-subtle',
                ].join(' ')}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
