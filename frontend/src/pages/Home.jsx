import { Link } from 'react-router-dom'
import { ArrowRight, FlaskConical, Sparkles } from 'lucide-react'
import PageShell from '../components/layout/PageShell'
import StatCard from '../components/ui/StatCard'
import Badge from '../components/ui/Badge'
import Card from '../components/ui/Card'

const SPARKLINE_TOTAL = [
  { value: 7 }, { value: 8 }, { value: 8 }, { value: 9 }, { value: 10 }, { value: 11 }, { value: 12 },
]
const SPARKLINE_LIFT = [
  { value: 6.2 }, { value: 7.1 }, { value: 7.8 }, { value: 7.5 }, { value: 8.2 }, { value: 8.5 }, { value: 8.7 },
]

const EXPERIMENTS = [
  {
    id: 'exp-001',
    name: 'Checkout Button Colour',
    metric: 'Checkout Conversion',
    status: 'completed',
    result: 'significant',
    lift: +12.4,
    pValue: 0.003,
    ci: [8.1, 16.7],
    subjects: 24580,
    days: 14,
  },
  {
    id: 'exp-002',
    name: 'Homepage Hero Copy',
    metric: 'Sign-up Rate',
    status: 'running',
    result: null,
    lift: +3.2,
    pValue: 0.12,
    ci: [-1.1, 7.5],
    subjects: 8920,
    days: 6,
  },
  {
    id: 'exp-003',
    name: 'Pricing Page Layout',
    metric: 'Pro Plan Conversion',
    status: 'completed',
    result: 'not-significant',
    lift: -1.8,
    pValue: 0.43,
    ci: [-5.2, 1.6],
    subjects: 15340,
    days: 21,
  },
]

const DEMOS = [
  {
    name: 'ecommerce',
    title: 'E-Commerce',
    description: 'Checkout flow A/B test across 50K users. Measures conversion and revenue per session.',
    metric: 'Checkout Conversion',
    n: '50,000',
  },
  {
    name: 'saas',
    title: 'SaaS',
    description: 'Trial-to-paid conversion experiment comparing onboarding flows across user cohorts.',
    metric: 'Trial Conversion',
    n: '12,400',
  },
  {
    name: 'marketplace',
    title: 'Marketplace',
    description: 'Listing page CTR optimization — tests headline formatting and image placement.',
    metric: 'Click-through Rate',
    n: '31,200',
  },
]

function fmt(n) {
  return new Intl.NumberFormat().format(n)
}

function ExperimentCard({ experiment: exp }) {
  const accentColor =
    exp.result === 'significant' ? 'green'
    : exp.result === 'not-significant' ? 'blue'
    : 'blue'

  const badgeVariant = exp.status === 'running' ? 'running' : (exp.result ?? 'draft')

  return (
    <Link to={`/experiments/${exp.id}`} className="block group">
      <Card
        variant="accent"
        accentColor={accentColor}
        className="p-5 hover:border-active hover:bg-elevated transition-all duration-150 cursor-pointer h-full"
      >
        <div className="flex items-start justify-between gap-2 mb-3">
          <h3 className="font-display font-bold text-[15px] text-primary leading-tight group-hover:text-data transition-colors">
            {exp.name}
          </h3>
          <Badge variant={badgeVariant} />
        </div>

        <p className="text-xs text-secondary mb-4 uppercase tracking-wide">{exp.metric}</p>

        <div className="grid grid-cols-3 gap-3 mb-4">
          <div>
            <p className="font-mono text-lg font-medium leading-none mb-1"
              style={{ color: exp.lift >= 0 ? 'var(--color-accent-green)' : 'var(--color-accent-red)' }}>
              {exp.lift >= 0 ? '+' : ''}{exp.lift}%
            </p>
            <p className="text-[10px] text-muted uppercase tracking-wide">Lift</p>
          </div>
          <div>
            <p className="font-mono text-lg font-medium text-primary leading-none mb-1">
              {exp.pValue}
            </p>
            <p className="text-[10px] text-muted uppercase tracking-wide">p-value</p>
          </div>
          <div>
            <p className="font-mono text-xs font-medium text-secondary leading-none mb-1 pt-0.5">
              [{exp.ci[0]}, {exp.ci[1]}]%
            </p>
            <p className="text-[10px] text-muted uppercase tracking-wide">95% CI</p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-[11px] text-muted border-t border-subtle pt-3">
          <span>{fmt(exp.subjects)} subjects</span>
          <span className="opacity-40">·</span>
          <span>{exp.days} days</span>
          <span className="opacity-40">·</span>
          <span className="capitalize">{exp.status}</span>
        </div>
      </Card>
    </Link>
  )
}

function DemoCard({ demo }) {
  return (
    <Link to={`/demo/${demo.name}`} className="block group">
      <Card className="p-5 hover:bg-elevated hover:border-active transition-all duration-150 cursor-pointer">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles size={14} className="text-blue opacity-70" />
          <span className="text-xs text-secondary uppercase tracking-widest font-medium">
            Demo
          </span>
        </div>
        <h3 className="font-display font-bold text-base text-primary mb-2 group-hover:text-data transition-colors">
          {demo.title}
        </h3>
        <p className="text-xs text-secondary leading-relaxed mb-3">{demo.description}</p>
        <div className="flex items-center justify-between text-[11px] text-muted">
          <span>{demo.metric}</span>
          <span>{demo.n} subjects</span>
        </div>
      </Card>
    </Link>
  )
}

export default function Home() {
  return (
    <PageShell>
      {/* ── Hero ───────────────────────────────────────── */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-3">
          <FlaskConical size={18} className="text-blue" />
          <span className="text-xs text-secondary uppercase tracking-widest font-medium">
            Intelligence Platform
          </span>
        </div>
        <h1 className="font-display text-3xl font-bold text-primary mb-2">
          Axiom
        </h1>
        <p className="text-secondary text-[15px] max-w-xl leading-relaxed">
          Design, run, and analyze A/B experiments with statistical rigor
          and Claude AI-assisted insights.
        </p>
      </div>

      {/* ── Stat cards ─────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
        <StatCard
          label="Total Experiments"
          value="12"
          trend={+20}
          sparkline={SPARKLINE_TOTAL}
        />
        <StatCard label="Live Now" value="2" />
        <StatCard label="Completed" value="8" />
        <StatCard
          label="Avg Lift (significant)"
          value="+8.7%"
          trend={+0.5}
          sparkline={SPARKLINE_LIFT}
        />
      </div>

      {/* ── Recent experiments ─────────────────────────── */}
      <section className="mb-10">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-lg font-bold text-primary">
            Recent Experiments
          </h2>
          <Link
            to="/experiments"
            className="inline-flex items-center gap-1 text-sm text-secondary hover:text-primary transition-colors"
          >
            View all <ArrowRight size={13} />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {EXPERIMENTS.map((exp) => (
            <ExperimentCard key={exp.id} experiment={exp} />
          ))}
        </div>
      </section>

      {/* ── Demo datasets ──────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-lg font-bold text-primary">
            Demo Datasets
          </h2>
          <span className="text-xs text-muted">Pre-loaded sample experiments</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {DEMOS.map((demo) => (
            <DemoCard key={demo.name} demo={demo} />
          ))}
        </div>
      </section>
    </PageShell>
  )
}
