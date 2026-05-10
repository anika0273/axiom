import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, FlaskConical, Sparkles, Plus } from 'lucide-react'
import { formatDistanceToNowStrict } from 'date-fns'
import PageShell from '../components/layout/PageShell'
import StatCard from '../components/ui/StatCard'
import Badge from '../components/ui/Badge'
import Card from '../components/ui/Card'
import Skeleton from '../components/ui/Skeleton'
import EmptyState from '../components/ui/EmptyState'
import Button from '../components/ui/Button'

const API_BASE = 'http://localhost:8000'

// Demo dataset cards — local data, no API call needed
const DEMOS = [
  {
    name: 'ecommerce',
    title: 'E-Commerce',
    description: 'Checkout flow A/B test across 10K users. Demonstrates SRM detection, novelty decay, and mobile vs desktop HTE.',
    metric: 'Checkout Conversion',
    n: '10,000',
  },
  {
    name: 'saas',
    title: 'SaaS',
    description: 'Trial-to-paid conversion experiment comparing 14-day vs 30-day free trials across user cohorts.',
    metric: 'Trial Conversion',
    n: '5,000',
  },
  {
    name: 'marketplace',
    title: 'Marketplace',
    description: 'Seller fee reduction test measuring GMV impact across established and new seller segments.',
    metric: 'Gross Merchandise Value',
    n: '20,000',
  },
]

function relativeDate(iso) {
  if (!iso) return '—'
  try { return formatDistanceToNowStrict(new Date(iso), { addSuffix: true }) } catch { return '—' }
}

function accentForExperiment(exp) {
  const v = exp.latest_result?.overall_verdict
  if (v === 'INVALID') return 'red'
  if (v === 'NEEDS_REVIEW') return 'amber'
  if (exp.status === 'running') return 'blue'
  return 'blue'
}

function badgeForExperiment(exp) {
  if (exp.status === 'running') return 'running'
  if (exp.status === 'draft') return 'draft'
  const v = exp.latest_result?.overall_verdict
  if (v === 'INVALID') return 'invalid'
  if (v === 'NEEDS_REVIEW') return 'warning'
  return 'completed'
}

function ExperimentCard({ exp }) {
  return (
    <Link to={`/experiments/${exp.id}`} className="block group">
      <Card
        variant="accent"
        accentColor={accentForExperiment(exp)}
        className="p-5 hover:border-active hover:bg-elevated transition-all duration-150 cursor-pointer h-full flex flex-col"
      >
        <div className="flex items-start justify-between gap-2 mb-3">
          <h3
            className="font-display font-bold text-[15px] leading-tight transition-colors group-hover:text-data"
            style={{ color: 'var(--color-text-primary)' }}
          >
            {exp.name}
          </h3>
          <Badge variant={badgeForExperiment(exp)} />
        </div>

        {exp.description && (
          <p
            className="text-xs leading-relaxed mb-4 flex-1"
            style={{
              color: 'var(--color-text-secondary)',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {exp.description}
          </p>
        )}

        <div
          className="flex items-center gap-3 text-[11px] border-t border-subtle pt-3 mt-auto"
          style={{ color: 'var(--color-text-muted)' }}
        >
          <span className="capitalize">{exp.experiment_type ?? '—'}</span>
          <span className="opacity-40">·</span>
          <span>{relativeDate(exp.created_at)}</span>
        </div>
      </Card>
    </Link>
  )
}

function ExperimentCardSkeleton() {
  const shimmer = {
    background: 'linear-gradient(90deg, var(--color-bg-card) 25%, var(--color-bg-elevated) 50%, var(--color-bg-card) 75%)',
    backgroundSize: '200% 100%',
  }
  return (
    <div
      className="rounded-lg border border-subtle p-5 space-y-3"
      style={{ backgroundColor: 'var(--color-bg-card)', minHeight: 160 }}
    >
      <div className="flex justify-between items-start gap-2">
        <div className="h-4 rounded w-2/3 animate-shimmer" style={shimmer} />
        <div className="h-5 w-20 rounded-full animate-shimmer" style={shimmer} />
      </div>
      <div className="h-3 rounded w-full animate-shimmer" style={shimmer} />
      <div className="h-3 rounded w-5/6 animate-shimmer" style={shimmer} />
      <div className="h-3 rounded w-1/3 animate-shimmer mt-4" style={shimmer} />
    </div>
  )
}

function StatCardSkeleton() {
  return <Skeleton variant="card" className="h-28" />
}

function DemoCard({ demo }) {
  return (
    <Link to={`/demo/${demo.name}`} className="block group">
      <Card className="p-5 hover:bg-elevated hover:border-active transition-all duration-150 cursor-pointer">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles size={14} style={{ color: 'var(--color-accent-blue)', opacity: 0.7 }} />
          <span
            className="text-xs uppercase tracking-widest font-medium"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            Demo
          </span>
        </div>
        <h3
          className="font-display font-bold text-base mb-2 transition-colors group-hover:text-data"
          style={{ color: 'var(--color-text-primary)' }}
        >
          {demo.title}
        </h3>
        <p
          className="text-xs leading-relaxed mb-3"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          {demo.description}
        </p>
        <div
          className="flex items-center justify-between text-[11px]"
          style={{ color: 'var(--color-text-muted)' }}
        >
          <span>{demo.metric}</span>
          <span>{demo.n} subjects</span>
        </div>
      </Card>
    </Link>
  )
}

export default function Home() {
  const [experiments, setExperiments] = useState([])
  const [meta, setMeta] = useState(null)
  const [loading, setLoading] = useState(true)
  // Errors on the home page degrade to "--" rather than crashing
  const [fetchFailed, setFetchFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${API_BASE}/api/v1/experiments?page=1&page_size=50`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((json) => {
        if (cancelled) return
        setExperiments(json.data ?? [])
        setMeta(json.meta ?? null)
        setLoading(false)
      })
      .catch(() => {
        if (cancelled) return
        setFetchFailed(true)
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const total = meta?.total ?? 0
  const liveCount = experiments.filter((e) => e.status === 'running').length
  const completedCount = experiments.filter((e) => e.status === 'completed').length
  const recent = experiments.slice(0, 3)

  return (
    <PageShell>
      {/* ── Hero ─────────────────────────────────────────── */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-3">
          <FlaskConical size={18} style={{ color: 'var(--color-accent-blue)' }} />
          <span
            className="text-xs uppercase tracking-widest font-medium"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            Intelligence Platform
          </span>
        </div>
        <h1 className="font-display text-3xl font-bold mb-2" style={{ color: 'var(--color-text-primary)' }}>
          Axiom
        </h1>
        <p className="text-[15px] max-w-xl leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
          Design, run, and analyze A/B experiments with statistical rigor
          and Claude AI-assisted insights.
        </p>
      </div>

      {/* ── Stat cards ───────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
        {loading ? (
          [0, 1, 2, 3].map((i) => <StatCardSkeleton key={i} />)
        ) : (
          <>
            <StatCard
              label="Total Experiments"
              value={fetchFailed ? '—' : String(total)}
            />
            <StatCard
              label="Live Now"
              value={fetchFailed ? '—' : String(liveCount)}
            />
            <StatCard
              label="Completed"
              value={fetchFailed ? '—' : String(completedCount)}
            />
            <StatCard
              label="Avg Lift (significant)"
              value="—"
            />
          </>
        )}
      </div>

      {/* ── Recent experiments ───────────────────────────── */}
      <section className="mb-10">
        <div className="flex items-center justify-between mb-4">
          <h2
            className="font-display text-lg font-bold"
            style={{ color: 'var(--color-text-primary)' }}
          >
            Recent Experiments
          </h2>
          <Link
            to="/experiments"
            className="inline-flex items-center gap-1 text-sm transition-colors"
            style={{ color: 'var(--color-text-secondary)' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-text-primary)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-text-secondary)')}
          >
            View all <ArrowRight size={13} />
          </Link>
        </div>

        {/* Loading */}
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[0, 1, 2].map((i) => <ExperimentCardSkeleton key={i} />)}
          </div>
        )}

        {/* Empty state */}
        {!loading && recent.length === 0 && (
          <EmptyState
            icon={<FlaskConical size={40} />}
            heading="No experiments yet"
            description="Create your first experiment to get started, or explore a pre-loaded demo to see how Axiom analyses results."
            action={
              <div className="flex items-center gap-3">
                <Link to="/experiments/new">
                  <Button size="sm">
                    <Plus size={14} />
                    New Experiment
                  </Button>
                </Link>
                <Link to="/demo">
                  <Button variant="secondary" size="sm">
                    <Sparkles size={14} />
                    Try a Demo
                  </Button>
                </Link>
              </div>
            }
          />
        )}

        {/* Cards */}
        {!loading && recent.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {recent.map((exp) => (
              <ExperimentCard key={exp.id} exp={exp} />
            ))}
          </div>
        )}
      </section>

      {/* ── Demo datasets ────────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2
            className="font-display text-lg font-bold"
            style={{ color: 'var(--color-text-primary)' }}
          >
            Demo Datasets
          </h2>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Pre-loaded sample experiments
          </span>
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
