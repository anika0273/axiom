import { MessageSquare, BarChart2, CheckCircle, ArrowRight } from 'lucide-react'

const STEPS = [
  {
    number: '01',
    Icon: MessageSquare,
    title: 'Describe',
    description:
      'Tell Claude what you want to test in plain English. Axiom generates a statistically sound experiment plan — sample size, metrics, and guardrails included.',
    accentColor: 'var(--color-accent-blue)',
  },
  {
    number: '02',
    Icon: BarChart2,
    title: 'Analyze',
    description:
      'As results come in, Axiom runs z-tests, CUPED variance reduction, heterogeneous treatment effect analysis, and anomaly detection automatically.',
    accentColor: 'var(--color-accent-green)',
  },
  {
    number: '03',
    Icon: CheckCircle,
    title: 'Decide',
    description:
      'Claude interprets the results in plain English and generates a stakeholder report. You make the final call — Axiom never decides for you.',
    accentColor: 'var(--color-accent-amber)',
  },
]

export default function HowItWorksSection() {
  return (
    <section
      className="py-24 px-6"
      style={{ backgroundColor: 'var(--color-bg-deep)' }}
    >
      <div className="max-w-content mx-auto">
        {/* Label */}
        <p
          className="text-[10px] font-bold uppercase tracking-[0.18em] mb-4"
          style={{ color: 'var(--color-text-muted)' }}
        >
          How it works
        </p>

        {/* Heading */}
        <h2
          className="font-display font-bold mb-16"
          style={{
            fontSize: 'clamp(24px, 3vw, 36px)',
            color: 'var(--color-text-primary)',
          }}
        >
          From idea to decision in three steps.
        </h2>

        {/* Steps */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-0 md:gap-0 relative">
          {STEPS.map(({ number, Icon, title, description, accentColor }, idx) => (
            <div key={title} className="relative flex md:flex-col items-start md:items-start gap-4 md:gap-0 mb-10 md:mb-0 md:pr-8">
              {/* Connector arrow — desktop only, between steps */}
              {idx < STEPS.length - 1 && (
                <div
                  className="hidden md:flex absolute top-5 right-0 items-center"
                  style={{ transform: 'translateX(50%)' }}
                >
                  <ArrowRight
                    size={16}
                    style={{ color: 'var(--color-border-active)' }}
                  />
                </div>
              )}

              {/* Step number + icon */}
              <div className="flex-shrink-0 flex md:flex-col items-center md:items-start gap-3 md:gap-0 md:mb-5">
                <div
                  className="w-11 h-11 rounded-full flex items-center justify-center flex-shrink-0"
                  style={{
                    border: `2px solid ${accentColor}`,
                    backgroundColor: `color-mix(in srgb, ${accentColor} 10%, transparent)`,
                  }}
                >
                  <Icon size={18} style={{ color: accentColor }} />
                </div>
                <span
                  className="font-mono text-xs font-bold md:mt-3 md:block"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  {number}
                </span>
              </div>

              {/* Text */}
              <div className="md:mt-0">
                <h3
                  className="font-display font-bold text-[17px] mb-2"
                  style={{ color: 'var(--color-text-primary)' }}
                >
                  {title}
                </h3>
                <p
                  className="text-[13px] leading-relaxed"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
