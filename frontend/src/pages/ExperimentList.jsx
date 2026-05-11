import { useState, useMemo, useRef, useCallback, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Plus,
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  FlaskConical,
  Sparkles,
  ArrowRight,
} from 'lucide-react'
import { formatDistanceToNowStrict, differenceInDays } from 'date-fns'

import PageShell from '../components/layout/PageShell'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Skeleton from '../components/ui/Skeleton'
import EmptyState from '../components/ui/EmptyState'
import NetworkError from '../components/errors/NetworkError'
import APIError from '../components/errors/APIError'

const API_BASE = 'http://localhost:8000'
const PAGE_SIZE = 10
const FETCH_LIMIT = 100

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function relativeDate(iso) {
  if (!iso) return '—'
  try { return formatDistanceToNowStrict(new Date(iso), { addSuffix: true }) }
  catch { return '—' }
}


const STATUS_DOT_COLOR = {
  running: 'var(--color-accent-green)',
  completed: 'var(--color-text-muted)',
  draft: 'var(--color-border-active)',
}

const SORT_LABELS = {
  newest: 'Newest',
  oldest: 'Oldest',
  lift: 'Highest Lift',
  significance: 'Most Significant',
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function LiftBadge({ liftPct }) {
  if (liftPct == null) return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  const positive = liftPct >= 0
  return (
    <span
      className="inline-flex items-center font-mono text-xs font-semibold px-1.5 py-0.5 rounded"
      style={{
        color: positive ? 'var(--color-accent-green)' : 'var(--color-accent-red)',
        backgroundColor: positive ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
      }}
    >
      {positive ? '+' : ''}{liftPct.toFixed(1)}%
    </span>
  )
}

function RunningProgress({ exp }) {
  const daysRunning = exp.start_date
    ? differenceInDays(new Date(), new Date(exp.start_date))
    : null
  const estimatedDays = exp.estimated_days ?? exp.expected_days ?? null
  const pct =
    daysRunning != null && estimatedDays
      ? Math.min(100, Math.round((daysRunning / estimatedDays) * 100))
      : null

  return (
    <div>
      {pct != null ? (
        <>
          <div className="flex items-center gap-2 mb-1">
            <div
              className="flex-1 h-1.5 rounded-full overflow-hidden"
              style={{ backgroundColor: 'var(--color-border-subtle)' }}
            >
              <div
                className="h-full rounded-full"
                style={{ width: `${pct}%`, backgroundColor: 'var(--color-accent-blue)' }}
              />
            </div>
            <span className="font-mono text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
              {pct}%
            </span>
          </div>
          <p className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
            Day {daysRunning} of est. {estimatedDays}
          </p>
        </>
      ) : (
        <p className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
          {daysRunning != null ? `Day ${daysRunning}` : 'Running'}
        </p>
      )}
    </div>
  )
}

function MetricPill({ name }) {
  if (!name) return null
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full font-mono text-[11px] truncate max-w-[140px]"
      style={{
        backgroundColor: 'rgba(59,130,246,0.08)',
        border: '1px solid rgba(59,130,246,0.2)',
        color: 'var(--color-text-data)',
      }}
      title={name}
    >
      {name}
    </span>
  )
}

function TypeBadge({ type }) {
  if (!type) return null
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded font-mono text-[11px]"
      style={{
        backgroundColor: 'var(--color-bg-elevated)',
        border: '1px solid var(--color-border-subtle)',
        color: 'var(--color-text-muted)',
      }}
    >
      {type}
    </span>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Experiment Row
// ─────────────────────────────────────────────────────────────────────────────

function ExperimentRow({ exp }) {
  const navigate = useNavigate()
  const dot = STATUS_DOT_COLOR[exp.status] ?? STATUS_DOT_COLOR.completed
  const isRunning = exp.status === 'running'
  const isCompleted = exp.status === 'completed'
  const isDraft = exp.status === 'draft'

  const liftPct = exp.latest_result?.lift_pct ?? exp.latest_result?.lift_pct_abs ?? null
  const isSignificant = exp.latest_result?.is_significant ?? null
  const sigVariant = isSignificant === true ? 'significant' : isSignificant === false ? 'not-significant' : null

  const metricName =
    exp.primary_metric_name ?? exp.primary_metric ?? exp.metric ?? null

  return (
    <div
      role="row"
      tabIndex={0}
      className="flex items-center gap-4 px-5 py-4 border-b border-subtle last:border-0 cursor-pointer transition-colors duration-100"
      onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--color-bg-elevated)')}
      onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '')}
      onClick={() => navigate(`/experiments/${exp.id}`)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          navigate(`/experiments/${exp.id}`)
        }
      }}
      aria-label={`Experiment: ${exp.name}`}
    >
      {/* Status dot */}
      <div
        className="flex-shrink-0 rounded-full"
        style={{
          width: 8,
          height: 8,
          backgroundColor: dot,
          boxShadow: isRunning ? `0 0 6px ${dot}` : 'none',
        }}
        aria-hidden="true"
      />

      {/* Left: name + hypothesis */}
      <div className="flex-1 min-w-0">
        <p
          className="font-display font-medium text-sm truncate"
          style={{ color: 'var(--color-text-primary)' }}
        >
          {exp.name}
        </p>
        {(exp.hypothesis ?? exp.description) && (
          <p
            className="text-xs mt-0.5 truncate"
            style={{ color: 'var(--color-text-muted)' }}
            title={exp.hypothesis ?? exp.description}
          >
            {exp.hypothesis ?? exp.description}
          </p>
        )}
      </div>

      {/* Center: metric pill + type badge */}
      <div className="hidden md:flex items-center gap-1.5 flex-shrink-0">
        <MetricPill name={metricName} />
        <TypeBadge type={exp.experiment_type} />
      </div>

      {/* Right: status-specific content */}
      <div className="flex-shrink-0 w-44 text-right">
        {isCompleted && (
          <div className="flex flex-col items-end gap-1">
            <div className="flex items-center gap-1.5">
              <LiftBadge liftPct={liftPct} />
              {sigVariant && (
                <Badge
                  variant={sigVariant}
                  label={isSignificant ? 'Significant' : 'Not sig.'}
                />
              )}
            </div>
            <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              {relativeDate(exp.updated_at ?? exp.created_at)}
            </span>
          </div>
        )}

        {isRunning && (
          <div className="flex justify-end">
            <div className="w-36 text-right">
              <RunningProgress exp={exp} />
            </div>
          </div>
        )}

        {isDraft && (
          <button
            className="inline-flex items-center gap-1 text-xs font-medium transition-colors"
            style={{ color: 'var(--color-text-data)' }}
            onClick={(e) => {
              e.stopPropagation()
              navigate(`/experiments/${exp.id}`)
            }}
            aria-label={`Configure experiment ${exp.name}`}
          >
            Configure
            <ArrowRight size={11} />
          </button>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Skeleton rows
// ─────────────────────────────────────────────────────────────────────────────

function ListRowSkeletons({ count = 5 }) {
  return Array.from({ length: count }).map((_, i) => (
    <Skeleton key={i} variant="list-row" />
  ))
}

// ─────────────────────────────────────────────────────────────────────────────
// Status filter tabs
// ─────────────────────────────────────────────────────────────────────────────

const TABS = ['all', 'running', 'completed', 'draft']

function FilterTabs({ active, counts, onChange }) {
  return (
    <div
      className="flex items-center gap-0 border-b border-subtle"
      role="tablist"
      aria-label="Filter by status"
    >
      {TABS.map((tab) => {
        const isActive = tab === active
        return (
          <button
            key={tab}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab)}
            className="relative px-4 py-2.5 text-xs font-medium capitalize transition-colors select-none hover:text-secondary"
            style={{
              color: isActive ? 'var(--color-accent-blue)' : 'var(--color-text-muted)',
            }}
          >
            {tab === 'all' ? 'All' : tab.charAt(0).toUpperCase() + tab.slice(1)}
            {counts[tab] > 0 && (
              <span
                className="ml-1.5"
                style={{
                  color: isActive ? 'var(--color-accent-blue)' : 'var(--color-text-muted)',
                  opacity: isActive ? 1 : 0.6,
                }}
              >
                ({counts[tab]})
              </span>
            )}
            {isActive && (
              <span
                className="absolute bottom-0 left-0 right-0 h-0.5 rounded-t-full"
                style={{ backgroundColor: 'var(--color-accent-blue)' }}
              />
            )}
          </button>
        )
      })}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Sort dropdown
// ─────────────────────────────────────────────────────────────────────────────

function SortDropdown({ value, onChange }) {
  return (
    <div className="relative flex-shrink-0">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none pl-3 pr-8 h-7 rounded-md text-xs font-medium cursor-pointer transition-colors"
        style={{
          backgroundColor: 'var(--color-bg-elevated)',
          border: '1px solid var(--color-border-subtle)',
          color: 'var(--color-text-secondary)',
        }}
        aria-label="Sort experiments"
      >
        {Object.entries(SORT_LABELS).map(([val, label]) => (
          <option key={val} value={val} style={{ backgroundColor: 'var(--color-bg-card)' }}>
            {label}
          </option>
        ))}
      </select>
      <ChevronDown
        size={12}
        className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2"
        style={{ color: 'var(--color-text-muted)' }}
        aria-hidden="true"
      />
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Pagination
// ─────────────────────────────────────────────────────────────────────────────

function Pagination({ page, total, onPage }) {
  const totalPages = Math.ceil(total / PAGE_SIZE)
  if (totalPages <= 1) return null
  const start = (page - 1) * PAGE_SIZE + 1
  const end = Math.min(page * PAGE_SIZE, total)

  return (
    <div className="flex items-center justify-between mt-4 px-1">
      <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
        Showing {start}–{end} of {total} experiment{total !== 1 ? 's' : ''}
      </span>
      <div className="flex items-center gap-1">
        <Button
          variant="secondary"
          size="sm"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          aria-label="Previous page"
        >
          <ChevronLeft size={13} />
          Prev
        </Button>

        {/* Page pills — show at most 5 */}
        {Array.from({ length: totalPages }, (_, i) => i + 1)
          .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
          .reduce((acc, p, idx, arr) => {
            if (idx > 0 && p - arr[idx - 1] > 1) acc.push('…')
            acc.push(p)
            return acc
          }, [])
          .map((p, i) =>
            p === '…' ? (
              <span
                key={`ellipsis-${i}`}
                className="px-2 text-xs"
                style={{ color: 'var(--color-text-muted)' }}
              >
                …
              </span>
            ) : (
              <button
                key={p}
                onClick={() => onPage(p)}
                className="w-7 h-7 rounded-md text-xs font-mono font-medium transition-colors"
                style={{
                  backgroundColor:
                    p === page ? 'var(--color-accent-blue)' : 'var(--color-bg-elevated)',
                  color: p === page ? 'white' : 'var(--color-text-secondary)',
                  border: '1px solid',
                  borderColor: p === page ? 'var(--color-accent-blue)' : 'var(--color-border-subtle)',
                }}
                aria-label={`Page ${p}`}
                aria-current={p === page ? 'page' : undefined}
              >
                {p}
              </button>
            )
          )}

        <Button
          variant="secondary"
          size="sm"
          disabled={page >= totalPages}
          onClick={() => onPage(page + 1)}
          aria-label="Next page"
        >
          Next
          <ChevronRight size={13} />
        </Button>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────────────────

export default function ExperimentList() {
  const [allExperiments, setAllExperiments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchRaw, setSearchRaw] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sortBy, setSortBy] = useState('newest')
  const [page, setPage] = useState(1)
  const searchInputRef = useRef(null)

  // Debounce search 200 ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchRaw)
      setPage(1)
    }, 200)
    return () => clearTimeout(timer)
  }, [searchRaw])

  // Reset page when filter/sort changes
  useEffect(() => { setPage(1) }, [statusFilter, sortBy])

  // Fetch all experiments (client-side filtering for speed)
  const fetchExperiments = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/experiments?page=1&page_size=${FETCH_LIMIT}`,
      )
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try { const b = await res.json(); msg = b?.error?.message ?? msg } catch {}
        const err = new Error(msg)
        err.status = res.status
        throw err
      }
      const json = await res.json()
      setAllExperiments(json.data ?? [])
    } catch (err) {
      let errorType = 'api_error'
      if (!navigator.onLine) errorType = 'network'
      else if (!err.status) errorType = 'network'
      else if (err.status >= 500) errorType = 'server_error'
      setError({ message: err.message, status: err.status, errorType })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchExperiments() }, [fetchExperiments])

  // Status tab counts — based on full dataset, not filtered
  const counts = useMemo(() => ({
    all: allExperiments.length,
    running: allExperiments.filter((e) => e.status === 'running').length,
    completed: allExperiments.filter((e) => e.status === 'completed').length,
    draft: allExperiments.filter((e) => e.status === 'draft').length,
  }), [allExperiments])

  // Filter → sort → paginate (all in memory)
  const filtered = useMemo(() => {
    let exps = allExperiments

    if (statusFilter !== 'all') {
      exps = exps.filter((e) => e.status === statusFilter)
    }

    if (search.trim()) {
      const q = search.toLowerCase()
      exps = exps.filter(
        (e) =>
          e.name?.toLowerCase().includes(q) ||
          e.description?.toLowerCase().includes(q) ||
          e.hypothesis?.toLowerCase().includes(q),
      )
    }

    return [...exps].sort((a, b) => {
      if (sortBy === 'newest') return new Date(b.created_at) - new Date(a.created_at)
      if (sortBy === 'oldest') return new Date(a.created_at) - new Date(b.created_at)
      if (sortBy === 'lift') {
        const la = a.latest_result?.lift_pct ?? -Infinity
        const lb = b.latest_result?.lift_pct ?? -Infinity
        return lb - la
      }
      if (sortBy === 'significance') {
        const pa = a.latest_result?.p_value ?? Infinity
        const pb = b.latest_result?.p_value ?? Infinity
        return pa - pb
      }
      return 0
    })
  }, [allExperiments, statusFilter, search, sortBy])

  const paginatedExps = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const isEmptyFiltered = !loading && !error && filtered.length === 0
  const noExperimentsAtAll = !loading && !error && allExperiments.length === 0

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
      <div className="flex items-center gap-3 mb-6">
        <h1
          className="font-display text-2xl font-bold"
          style={{ color: 'var(--color-text-primary)' }}
        >
          Experiments
        </h1>
        {!loading && !error && (
          <span
            className="inline-flex items-center justify-center font-mono text-[11px] font-medium h-5 min-w-[20px] px-1.5 rounded-full"
            style={{
              backgroundColor: 'var(--color-bg-elevated)',
              color: 'var(--color-text-muted)',
              border: '1px solid var(--color-border-subtle)',
            }}
          >
            {allExperiments.length}
          </span>
        )}
      </div>

      {/* Error state */}
      {error && error.errorType === 'network' && (
        <NetworkError onRetry={fetchExperiments} />
      )}
      {error && error.errorType !== 'network' && (
        <APIError
          code={error.status ? `HTTP ${error.status}` : undefined}
          message={error.message}
          onRetry={fetchExperiments}
        />
      )}

      {/* No experiments at all empty state */}
      {noExperimentsAtAll && (
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

      {/* Filter bar + list (shown once we have data or are loading) */}
      {!error && !noExperimentsAtAll && (
        <>
          {/* Filter bar */}
          <div className="mb-4">
            {/* Search + sort row */}
            <div className="flex items-center gap-3 mb-3">
              {/* Search */}
              <div className="relative flex-1 max-w-xs">
                <Search
                  size={13}
                  className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                  style={{ color: 'var(--color-text-muted)' }}
                  aria-hidden="true"
                />
                <input
                  ref={searchInputRef}
                  data-search-input="true"
                  type="search"
                  placeholder="Search experiments…"
                  value={searchRaw}
                  onChange={(e) => setSearchRaw(e.target.value)}
                  className="w-full h-7 pl-8 pr-3 rounded-md text-xs transition-colors"
                  style={{
                    backgroundColor: 'var(--color-bg-elevated)',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text-primary)',
                    '::placeholder': { color: 'var(--color-text-muted)' },
                  }}
                  aria-label="Search experiments"
                />
              </div>

              <div className="ml-auto">
                <SortDropdown value={sortBy} onChange={setSortBy} />
              </div>
            </div>

            {/* Status tabs */}
            {!loading && (
              <FilterTabs
                active={statusFilter}
                counts={counts}
                onChange={(tab) => setStatusFilter(tab)}
              />
            )}
          </div>

          {/* Loading skeleton list */}
          {loading && (
            <div
              className="border border-subtle rounded-lg overflow-hidden"
              aria-busy="true"
              aria-label="Loading experiments"
            >
              <ListRowSkeletons count={5} />
            </div>
          )}

          {/* Filtered empty state */}
          {isEmptyFiltered && !noExperimentsAtAll && (
            <div className="py-16 text-center">
              <p
                className="font-display font-bold mb-1"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                No experiments match
              </p>
              <p className="text-sm mb-4" style={{ color: 'var(--color-text-muted)' }}>
                Try adjusting your search or filter.
              </p>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => { setSearchRaw(''); setStatusFilter('all') }}
              >
                Clear filters
              </Button>
            </div>
          )}

          {/* Experiment list */}
          {!loading && paginatedExps.length > 0 && (
            <>
              <div
                className="border border-subtle rounded-lg overflow-hidden"
                role="table"
                aria-label="Experiments"
              >
                {paginatedExps.map((exp) => (
                  <ExperimentRow key={exp.id} exp={exp} />
                ))}
              </div>

              <Pagination
                page={page}
                total={filtered.length}
                onPage={(p) => { setPage(p); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
              />
            </>
          )}
        </>
      )}
    </PageShell>
  )
}
