import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Plus, ArrowRight, FlaskConical, RefreshCw, ChevronLeft, ChevronRight, Sparkles } from 'lucide-react'
import { formatDistanceToNowStrict } from 'date-fns'
import PageShell from '../components/layout/PageShell'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Skeleton from '../components/ui/Skeleton'
import EmptyState from '../components/ui/EmptyState'

const API_BASE = 'http://localhost:8000'
const PAGE_SIZE = 20

/** Map API experiment fields to a Badge variant. */
function badgeVariant(exp) {
  if (exp.status === 'running') return 'running'
  if (exp.status === 'draft') return 'draft'
  const v = exp.latest_result?.overall_verdict
  if (v === 'INVALID') return 'invalid'
  if (v === 'NEEDS_REVIEW') return 'warning'
  return 'completed'
}

/** Format experiment_type for the Type column. */
function fmtType(type) {
  if (type === 'proportion') return 'Proportion'
  if (type === 'mean') return 'Mean'
  return type ?? '—'
}

/** Relative time — "3 days ago". */
function relativeDate(iso) {
  if (!iso) return '—'
  try {
    return formatDistanceToNowStrict(new Date(iso), { addSuffix: true })
  } catch {
    return '—'
  }
}

function SkeletonRows({ count = 6 }) {
  return Array.from({ length: count }).map((_, i) => (
    <Skeleton key={i} variant="table-row" className="px-5" />
  ))
}

function ErrorCard({ message, onRetry }) {
  return (
    <div
      className="rounded-lg border p-6 flex items-start gap-4"
      style={{
        borderColor: 'rgba(239,68,68,0.25)',
        borderLeftWidth: 3,
        borderLeftColor: 'var(--color-accent-red)',
        backgroundColor: 'rgba(239,68,68,0.05)',
      }}
    >
      <div className="flex-1">
        <p className="font-medium text-sm mb-1" style={{ color: 'var(--color-text-primary)' }}>
          Failed to load experiments
        </p>
        <p className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          {message ?? 'An unexpected error occurred.'}
        </p>
      </div>
      <Button variant="secondary" size="sm" onClick={onRetry}>
        <RefreshCw size={13} />
        Retry
      </Button>
    </div>
  )
}

function Pagination({ page, pageSize, total, onPage }) {
  const totalPages = Math.ceil(total / pageSize)
  if (totalPages <= 1) return null
  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)

  return (
    <div className="flex items-center justify-between mt-4 px-1">
      <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
        Showing {start}–{end} of {total}
      </span>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          <ChevronLeft size={14} />
          Prev
        </Button>
        <span className="font-mono text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          {page} / {totalPages}
        </span>
        <Button
          variant="secondary"
          size="sm"
          disabled={page >= totalPages}
          onClick={() => onPage(page + 1)}
        >
          Next
          <ChevronRight size={14} />
        </Button>
      </div>
    </div>
  )
}

export default function ExperimentList() {
  const [experiments, setExperiments] = useState([])
  const [meta, setMeta] = useState({ total: 0, page: 1, page_size: PAGE_SIZE })
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchExperiments = useCallback(async (p) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/experiments?page=${p}&page_size=${PAGE_SIZE}`,
      )
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try { const b = await res.json(); msg = b?.error?.message ?? msg } catch {}
        throw new Error(msg)
      }
      const json = await res.json()
      setExperiments(json.data ?? [])
      setMeta(json.meta ?? { total: 0, page: p, page_size: PAGE_SIZE })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchExperiments(page) }, [page, fetchExperiments])

  const handlePage = (p) => { setPage(p); window.scrollTo(0, 0) }
  const running = experiments.filter((e) => e.status === 'running').length

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
      {/* Page heading */}
      <div className="mb-6">
        <h1 className="font-display text-2xl font-bold mb-1" style={{ color: 'var(--color-text-primary)' }}>
          Experiments
        </h1>
        {!loading && !error && (
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            {meta.total} experiment{meta.total !== 1 ? 's' : ''}
            {running > 0 && ` · ${running} running`}
          </p>
        )}
      </div>

      {/* Error state */}
      {error && <ErrorCard message={error} onRetry={() => fetchExperiments(page)} />}

      {/* Loading state */}
      {loading && !error && (
        <div className="border border-subtle rounded-lg overflow-hidden">
          <TableHeader />
          <SkeletonRows count={6} />
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && experiments.length === 0 && (
        <EmptyState
          icon={<FlaskConical size={40} />}
          heading="No experiments yet"
          description="Create your first experiment to get started, or explore a demo to see how Axiom analyses results."
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

      {/* Experiments table */}
      {!loading && !error && experiments.length > 0 && (
        <>
          <div className="border border-subtle rounded-lg overflow-hidden">
            <TableHeader />
            {experiments.map((exp) => (
              <ExperimentRow key={exp.id} exp={exp} />
            ))}
          </div>
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={meta.total}
            onPage={handlePage}
          />
        </>
      )}
    </PageShell>
  )
}

function TableHeader() {
  return (
    <div
      className="grid gap-4 px-5 py-3 border-b border-subtle text-[11px] uppercase tracking-widest font-medium"
      style={{
        gridTemplateColumns: '2fr 1fr 1fr 1fr auto',
        backgroundColor: 'var(--color-bg-elevated)',
        color: 'var(--color-text-muted)',
      }}
    >
      <span>Experiment</span>
      <span>Type</span>
      <span>Status</span>
      <span>Created</span>
      <span />
    </div>
  )
}

function ExperimentRow({ exp }) {
  return (
    <div
      className="grid gap-4 px-5 py-3.5 border-b border-subtle last:border-0 items-center transition-colors duration-100 hover:bg-elevated"
      style={{ gridTemplateColumns: '2fr 1fr 1fr 1fr auto' }}
    >
      {/* Name + description */}
      <div className="min-w-0">
        <Link
          to={`/experiments/${exp.id}`}
          className="font-medium text-sm block truncate transition-colors"
          style={{ color: 'var(--color-text-primary)' }}
          onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-text-data)')}
          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-text-primary)')}
        >
          {exp.name}
        </Link>
        {exp.description && (
          <p
            className="text-xs mt-0.5 truncate"
            style={{ color: 'var(--color-text-muted)' }}
            title={exp.description}
          >
            {exp.description}
          </p>
        )}
      </div>

      {/* Type */}
      <span
        className="font-mono text-xs"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        {fmtType(exp.experiment_type)}
      </span>

      {/* Status badge */}
      <span>
        <Badge variant={badgeVariant(exp)} />
      </span>

      {/* Created date */}
      <span
        className="text-xs"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {relativeDate(exp.created_at)}
      </span>

      {/* Action */}
      <Link to={`/experiments/${exp.id}`}>
        <Button variant="ghost" size="sm">
          <ArrowRight size={14} />
        </Button>
      </Link>
    </div>
  )
}
