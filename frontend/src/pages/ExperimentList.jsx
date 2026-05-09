import { Link } from 'react-router-dom'
import { Plus, ArrowRight } from 'lucide-react'
import PageShell from '../components/layout/PageShell'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'

const EXPERIMENTS = [
  { id: 'exp-001', name: 'Checkout Button Colour', metric: 'Checkout Conversion', status: 'completed', result: 'significant', lift: +12.4, pValue: 0.003, subjects: 24580, days: 14 },
  { id: 'exp-002', name: 'Homepage Hero Copy', metric: 'Sign-up Rate', status: 'running', result: null, lift: +3.2, pValue: 0.12, subjects: 8920, days: 6 },
  { id: 'exp-003', name: 'Pricing Page Layout', metric: 'Pro Plan Conversion', status: 'completed', result: 'not-significant', lift: -1.8, pValue: 0.43, subjects: 15340, days: 21 },
  { id: 'exp-004', name: 'Search Autocomplete', metric: 'Search-to-click Rate', status: 'completed', result: 'significant', lift: +5.9, pValue: 0.01, subjects: 33100, days: 10 },
  { id: 'exp-005', name: 'Mobile Nav Redesign', metric: 'Session Duration', status: 'draft', result: null, lift: null, pValue: null, subjects: 0, days: 0 },
  { id: 'exp-006', name: 'Email Subject Lines', metric: 'Open Rate', status: 'running', result: null, lift: +8.1, pValue: 0.06, subjects: 5200, days: 3 },
]

function fmt(n) {
  return n != null ? new Intl.NumberFormat().format(n) : '—'
}

function LiftCell({ lift }) {
  if (lift == null) return <span className="text-muted font-mono text-sm">—</span>
  return (
    <span
      className="font-mono text-sm font-medium"
      style={{ color: lift >= 0 ? 'var(--color-accent-green)' : 'var(--color-accent-red)' }}
    >
      {lift >= 0 ? '+' : ''}{lift}%
    </span>
  )
}

export default function ExperimentList() {
  return (
    <PageShell
      breadcrumbs={[{ label: 'Experiments' }]}
      actions={
        <Link to="/experiments/new">
          <Button size="sm">
            <Plus size={14} />
            New Experiment
          </Button>
        </Link>
      }
    >
      <div className="mb-6">
        <h1 className="font-display text-2xl font-bold text-primary mb-1">Experiments</h1>
        <p className="text-secondary text-sm">
          {EXPERIMENTS.length} experiments · {EXPERIMENTS.filter(e => e.status === 'running').length} running
        </p>
      </div>

      <div className="border border-subtle rounded-lg overflow-hidden">
        {/* Table header */}
        <div className="grid grid-cols-[2fr_1.5fr_1fr_1fr_1fr_1fr_auto] gap-4 px-5 py-3 border-b border-subtle bg-elevated text-[11px] text-muted uppercase tracking-widest font-medium">
          <span>Experiment</span>
          <span>Metric</span>
          <span>Status</span>
          <span className="text-right">Lift</span>
          <span className="text-right">p-value</span>
          <span className="text-right">Subjects</span>
          <span />
        </div>

        {/* Rows */}
        {EXPERIMENTS.map((exp) => {
          const badgeVariant = exp.status === 'running' ? 'running'
            : exp.status === 'draft' ? 'draft'
            : (exp.result ?? 'completed')

          return (
            <div
              key={exp.id}
              className="grid grid-cols-[2fr_1.5fr_1fr_1fr_1fr_1fr_auto] gap-4 px-5 py-3.5 border-b border-subtle last:border-0 hover:bg-elevated transition-colors duration-100 items-center"
            >
              <div className="min-w-0">
                <Link
                  to={`/experiments/${exp.id}`}
                  className="font-medium text-sm text-primary hover:text-data transition-colors truncate block"
                >
                  {exp.name}
                </Link>
              </div>
              <span className="text-sm text-secondary truncate">{exp.metric}</span>
              <span><Badge variant={badgeVariant} /></span>
              <span className="text-right"><LiftCell lift={exp.lift} /></span>
              <span className="text-right font-mono text-sm text-secondary">
                {exp.pValue ?? '—'}
              </span>
              <span className="text-right font-mono text-sm text-secondary">{fmt(exp.subjects)}</span>
              <Link to={`/experiments/${exp.id}`}>
                <Button variant="ghost" size="sm">
                  <ArrowRight size={14} />
                </Button>
              </Link>
            </div>
          )
        })}
      </div>
    </PageShell>
  )
}
