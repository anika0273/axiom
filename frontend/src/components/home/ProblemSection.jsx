import { BarChart2, Eye, TrendingDown } from 'lucide-react'

const PROBLEMS = [
  {
    Icon: BarChart2,
    accentColor: 'var(--color-accent-red)',
    title: 'Underpowered tests',
    description:
      'Teams stop experiments early when results look good — before collecting enough data to be confident.',
  },
  {
    Icon: Eye,
    accentColor: 'var(--color-accent-amber)',
    title: 'Peeking at results',
    description:
      'Checking results daily inflates your false positive rate from 5% to over 50% over a 2-week test.',
  },
  {
    Icon: TrendingDown,
    accentColor: 'var(--color-accent-blue)',
    title: 'Averages hide the truth',
    description:
      'A feature that helps power users but hurts new users shows a small positive average — and gets shipped.',
  },
]

export default function ProblemSection() {
  function scrollToDemos() {
    document.getElementById('demos')?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <section
      className="py-24 px-6"
      style={{ backgroundColor: '#0F1724' }}
    >
      <div className="max-w-content mx-auto">
        {/* Label */}
        <p
          className="text-[10px] font-bold uppercase tracking-[0.18em] mb-4"
          style={{ color: 'var(--color-text-muted)' }}
        >
          The Problem
        </p>

        {/* Heading */}
        <h2
          className="font-display font-bold mb-14"
          style={{
            fontSize: 'clamp(26px, 3.5vw, 40px)',
            color: 'var(--color-text-primary)',
            lineHeight: 1.2,
          }}
        >
          Most A/B tests are statistically invalid.
        </h2>

        {/* Problem cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-14">
          {PROBLEMS.map(({ Icon, accentColor, title, description }) => (
            <div
              key={title}
              className="p-6 rounded-lg border border-subtle"
              style={{ backgroundColor: 'var(--color-bg-card)' }}
            >
              <div
                className="w-9 h-9 rounded-md flex items-center justify-center mb-4"
                style={{
                  backgroundColor: `color-mix(in srgb, ${accentColor} 12%, transparent)`,
                  border: `1px solid color-mix(in srgb, ${accentColor} 25%, transparent)`,
                }}
              >
                <Icon size={17} style={{ color: accentColor }} />
              </div>
              <h3
                className="font-display font-bold text-[15px] mb-2"
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
          ))}
        </div>

        {/* Divider + CTA */}
        <div
          className="border-t pt-10 text-center"
          style={{ borderColor: 'var(--color-border-subtle)' }}
        >
          <p
            className="text-sm"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            Axiom fixes all of this.{' '}
            <button
              onClick={scrollToDemos}
              className="underline underline-offset-2 transition-colors hover:opacity-80"
              style={{ color: 'var(--color-accent-blue)' }}
            >
              See it in action →
            </button>
          </p>
        </div>
      </div>
    </section>
  )
}
