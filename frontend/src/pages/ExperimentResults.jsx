import { useParams, Link } from 'react-router-dom'
import { FileText, RefreshCw, Zap } from 'lucide-react'
import PageShell from '../components/layout/PageShell'
import StatCard from '../components/ui/StatCard'
import Badge from '../components/ui/Badge'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Skeleton from '../components/ui/Skeleton'

// Mock data keyed by experiment id
const MOCK = {
  'exp-001': {
    name: 'Checkout Button Colour',
    status: 'completed',
    result: 'significant',
    metric: 'Checkout Conversion',
    lift: +12.4,
    pValue: 0.003,
    ci: [8.1, 16.7],
    subjects: 24580,
    controlRate: '3.82%',
    variantRate: '4.29%',
    days: 14,
    power: 0.91,
    sparkline: [
      { value: 3.0 }, { value: 3.4 }, { value: 4.1 }, { value: 4.0 },
      { value: 4.2 }, { value: 4.3 }, { value: 4.29 },
    ],
  },
}

function fmt(n) {
  return new Intl.NumberFormat().format(n)
}

export default function ExperimentResults() {
  const { id } = useParams()
  const exp = MOCK[id]

  if (!exp) {
    return (
      <PageShell
        breadcrumbs={[
          { label: 'Experiments', href: '/experiments' },
          { label: id },
        ]}
      >
        <div className="space-y-4 max-w-3xl">
          <Skeleton variant="card" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => <Skeleton key={i} variant="card" />)}
          </div>
          <Skeleton variant="chart" />
        </div>
      </PageShell>
    )
  }

  return (
    <PageShell
      breadcrumbs={[
        { label: 'Experiments', href: '/experiments' },
        { label: exp.name },
      ]}
      actions={
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm">
            <RefreshCw size={13} />
            Recompute
          </Button>
          <Link to={`/experiments/${id}/report`}>
            <Button size="sm">
              <FileText size={13} />
              Report
            </Button>
          </Link>
        </div>
      }
    >
      {/* Header */}
      <div className="mb-6 flex items-start gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <h1 className="font-display text-2xl font-bold text-primary mb-2">{exp.name}</h1>
          <div className="flex items-center gap-3 flex-wrap">
            <Badge variant={exp.status === 'running' ? 'running' : (exp.result ?? 'completed')} />
            <span className="text-sm text-secondary">{exp.metric}</span>
            <span className="text-xs text-muted">{exp.days} days · {fmt(exp.subjects)} subjects</span>
          </div>
        </div>
      </div>

      {/* Key stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Lift" value={`${exp.lift >= 0 ? '+' : ''}${exp.lift}%`} sparkline={exp.sparkline} />
        <StatCard label="p-value" value={exp.pValue} />
        <StatCard label="95% CI" value={`[${exp.ci[0]}, ${exp.ci[1]}]%`} />
        <StatCard label="Power" value={`${Math.round(exp.power * 100)}%`} />
      </div>

      {/* Conversion rates */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <Card className="p-5">
          <p className="text-xs text-muted uppercase tracking-widest mb-3">Control</p>
          <p className="font-mono text-3xl font-medium text-primary mb-1">{exp.controlRate}</p>
          <p className="text-sm text-secondary">{exp.metric}</p>
        </Card>
        <Card variant="accent" accentColor={exp.result === 'significant' ? 'green' : 'blue'} className="p-5">
          <p className="text-xs text-muted uppercase tracking-widest mb-3">Variant</p>
          <p className="font-mono text-3xl font-medium text-primary mb-1">{exp.variantRate}</p>
          <p className="text-sm text-secondary">{exp.metric}</p>
        </Card>
      </div>

      {/* AI Interpretation placeholder */}
      <Card variant="accent" accentColor="blue" className="p-6">
        <div className="flex items-center gap-2 mb-3">
          <Zap size={15} className="text-blue" />
          <h2 className="font-display font-bold text-base text-primary">Claude Interpretation</h2>
        </div>
        <p className="text-secondary text-sm leading-relaxed mb-4">
          The blue checkout button produced a statistically significant increase of{' '}
          <span className="text-data font-mono">+{exp.lift}%</span> in {exp.metric.toLowerCase()}{' '}
          (p = {exp.pValue}, 95% CI [{exp.ci[0]}%, {exp.ci[1]}%]). With {fmt(exp.subjects)} subjects
          and {Math.round(exp.power * 100)}% power, this result is reliable. The effect size is
          practically meaningful for this metric.
        </p>
        <div className="flex items-center gap-3 p-3 bg-elevated rounded-lg border border-subtle">
          <span className="text-[10px] text-muted uppercase tracking-widest font-medium">Recommendation</span>
          <span className="text-sm font-medium text-primary">Ship variant — effect is real and positive.</span>
        </div>
      </Card>
    </PageShell>
  )
}
