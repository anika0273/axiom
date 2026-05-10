import { Zap } from 'lucide-react'
import { formatDistanceToNow, parseISO, isValid } from 'date-fns'

/**
 * Document-style header for the stakeholder report.
 * @param {Object} props
 * @param {string} props.experimentName
 * @param {string|null} props.generatedAt - ISO timestamp
 */
export default function ReportHeader({ experimentName, generatedAt }) {
  let timeAgo = null
  if (generatedAt) {
    try {
      const date = parseISO(generatedAt)
      if (isValid(date)) timeAgo = formatDistanceToNow(date, { addSuffix: true })
    } catch {
      // ignore invalid date
    }
  }

  return (
    <div className="mb-10 pb-8 border-b border-subtle print:mb-6 print:pb-4">
      {/* Logo + label row */}
      <div className="flex items-center gap-2 mb-5">
        <div
          className="flex items-center justify-center w-6 h-6 rounded"
          style={{ backgroundColor: 'rgba(59,130,246,0.15)' }}
        >
          <Zap size={13} style={{ color: 'var(--color-accent-blue)' }} strokeWidth={2.5} />
        </div>
        <span
          className="text-[10px] uppercase tracking-[0.18em] font-semibold"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Axiom · Experiment Report
        </span>
      </div>

      {/* Experiment name */}
      <h1
        className="font-display font-bold leading-tight mb-4"
        style={{ fontSize: 28, color: 'var(--color-text-primary)' }}
      >
        {experimentName ?? 'Untitled Experiment'}
      </h1>

      {/* Meta row */}
      <div
        className="flex items-center flex-wrap gap-3 text-xs"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {timeAgo && (
          <span>Generated {timeAgo}</span>
        )}
        {timeAgo && (
          <span
            className="w-1 h-1 rounded-full inline-block"
            style={{ backgroundColor: 'var(--color-border-subtle)' }}
          />
        )}
        <span
          className="flex items-center gap-1"
          style={{ color: 'var(--color-accent-blue)' }}
        >
          <Zap size={10} strokeWidth={2.5} />
          Powered by Claude
        </span>
      </div>
    </div>
  )
}
