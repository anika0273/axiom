import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FlaskConical, Lightbulb, BarChart2, Users } from 'lucide-react'
import PageShell from '../components/layout/PageShell'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'

const STEPS = [
  { id: 1, label: 'Hypothesis', icon: Lightbulb },
  { id: 2, label: 'Metrics', icon: BarChart2 },
  { id: 3, label: 'Audience', icon: Users },
  { id: 4, label: 'Review', icon: FlaskConical },
]

export default function ExperimentNew() {
  const [step, setStep] = useState(1)
  const navigate = useNavigate()

  return (
    <PageShell
      breadcrumbs={[
        { label: 'Experiments', href: '/experiments' },
        { label: 'New Experiment' },
      ]}
    >
      <div className="max-w-2xl mx-auto">
        <div className="mb-8">
          <h1 className="font-display text-2xl font-bold text-primary mb-1">New Experiment</h1>
          <p className="text-secondary text-sm">
            Define your hypothesis, metrics, and audience before launching.
          </p>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-0 mb-8">
          {STEPS.map((s, i) => {
            const Icon = s.icon
            const isActive = s.id === step
            const isDone = s.id < step
            return (
              <div key={s.id} className="flex items-center flex-1 last:flex-none">
                <button
                  onClick={() => isDone && setStep(s.id)}
                  className={[
                    'flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-all',
                    isActive ? 'text-primary bg-elevated border border-active' : '',
                    isDone ? 'text-secondary hover:text-primary cursor-pointer' : '',
                    !isDone && !isActive ? 'text-muted cursor-default' : '',
                  ].join(' ')}
                >
                  <Icon size={14} />
                  <span className="hidden sm:inline">{s.label}</span>
                  <span className="sm:hidden">{s.id}</span>
                </button>
                {i < STEPS.length - 1 && (
                  <div className={`flex-1 h-px mx-2 ${isDone ? 'bg-active' : 'bg-subtle'}`} />
                )}
              </div>
            )
          })}
        </div>

        {/* Step content */}
        {step === 1 && (
          <Card className="p-6">
            <h2 className="font-display font-bold text-base text-primary mb-4">
              Define your hypothesis
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-secondary uppercase tracking-widest mb-2">
                  Experiment Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Checkout button colour test"
                  className="w-full bg-elevated border border-subtle rounded-md px-3 py-2.5 text-sm text-primary placeholder:text-muted focus:outline-none focus:border-active transition-colors"
                />
              </div>
              <div>
                <label className="block text-xs text-secondary uppercase tracking-widest mb-2">
                  Hypothesis
                </label>
                <textarea
                  rows={4}
                  placeholder="We believe that [change] will cause [outcome] for [audience] because [rationale]."
                  className="w-full bg-elevated border border-subtle rounded-md px-3 py-2.5 text-sm text-primary placeholder:text-muted focus:outline-none focus:border-active transition-colors resize-none"
                />
              </div>
              <div>
                <label className="block text-xs text-secondary uppercase tracking-widest mb-2">
                  Describe your change (for Claude AI planning)
                </label>
                <textarea
                  rows={3}
                  placeholder="Describe the change in plain English and Claude will suggest optimal experiment settings, sample size, and metrics..."
                  className="w-full bg-elevated border border-subtle rounded-md px-3 py-2.5 text-sm text-primary placeholder:text-muted focus:outline-none focus:border-active transition-colors resize-none"
                />
                <p className="text-[11px] text-muted mt-1">Claude AI will suggest experiment parameters based on your description.</p>
              </div>
            </div>
          </Card>
        )}

        {step === 2 && (
          <Card className="p-6">
            <h2 className="font-display font-bold text-base text-primary mb-1">Select metrics</h2>
            <p className="text-secondary text-sm mb-4">Choose a primary metric and up to 3 guardrail metrics.</p>
            <div className="space-y-3">
              {['Conversion Rate', 'Revenue per Session', 'Session Duration', 'Bounce Rate'].map((m) => (
                <label key={m} className="flex items-center gap-3 p-3 rounded-md border border-subtle hover:border-active cursor-pointer transition-colors">
                  <input type="radio" name="primary_metric" className="accent-blue" />
                  <span className="text-sm text-primary">{m}</span>
                </label>
              ))}
            </div>
          </Card>
        )}

        {step === 3 && (
          <Card className="p-6">
            <h2 className="font-display font-bold text-base text-primary mb-4">Audience &amp; traffic</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs text-secondary uppercase tracking-widest mb-2">Traffic Split</label>
                <div className="flex gap-3">
                  {['50/50', '80/20', '90/10'].map((split) => (
                    <label key={split} className="flex items-center gap-2 px-3 py-2 rounded-md border border-subtle hover:border-active cursor-pointer transition-colors text-sm text-secondary">
                      <input type="radio" name="split" className="accent-blue" />
                      {split}
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs text-secondary uppercase tracking-widest mb-2">Minimum Detectable Effect (%)</label>
                <input type="number" defaultValue={5} min={1} max={50}
                  className="w-32 bg-elevated border border-subtle rounded-md px-3 py-2.5 text-sm text-primary focus:outline-none focus:border-active transition-colors" />
              </div>
            </div>
          </Card>
        )}

        {step === 4 && (
          <Card className="p-6">
            <h2 className="font-display font-bold text-base text-primary mb-1">Review &amp; launch</h2>
            <p className="text-secondary text-sm mb-4">Your experiment is ready. Once launched, variant assignments are permanent.</p>
            <div className="space-y-2 mb-6 p-4 bg-elevated rounded-lg border border-subtle">
              <div className="flex justify-between text-sm">
                <span className="text-secondary">Name</span>
                <span className="text-primary font-medium">My Experiment</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-secondary">Primary metric</span>
                <span className="text-primary font-medium">Conversion Rate</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-secondary">Traffic split</span>
                <span className="text-primary font-medium">50 / 50</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-secondary">Est. sample size</span>
                <span className="font-mono text-data font-medium">~18,400 per variant</span>
              </div>
            </div>
          </Card>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between mt-6">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => step > 1 ? setStep(s => s - 1) : navigate('/experiments')}
          >
            {step > 1 ? '← Back' : 'Cancel'}
          </Button>
          <Button
            size="sm"
            onClick={() => step < STEPS.length ? setStep(s => s + 1) : navigate('/experiments/exp-001')}
          >
            {step < STEPS.length ? 'Continue →' : 'Launch Experiment'}
          </Button>
        </div>
      </div>
    </PageShell>
  )
}
