import { Link } from 'react-router-dom'
import { Sparkles } from 'lucide-react'

const VERDICT_STYLES = {
  NEEDS_REVIEW: {
    label: 'Needs Review',
    color: 'var(--color-accent-amber)',
    bg: 'rgba(245,158,11,0.08)',
    border: 'rgba(245,158,11,0.3)',
  },
  SIGNIFICANT: {
    label: 'Significant',
    color: 'var(--color-accent-green)',
    bg: 'rgba(16,185,129,0.08)',
    border: 'rgba(16,185,129,0.3)',
  },
  NOT_SIGNIFICANT: {
    label: 'Not significant',
    color: 'var(--color-text-muted)',
    bg: 'rgba(71,85,105,0.15)',
    border: 'rgba(71,85,105,0.4)',
  },
  INVALID: {
    label: 'Invalid',
    color: 'var(--color-accent-red)',
    bg: 'rgba(239,68,68,0.08)',
    border: 'rgba(239,68,68,0.3)',
  },
}

/**
 * @param {Object} props
 * @param {string} props.slug - Route slug (ecommerce | saas | marketplace)
 * @param {string} props.title
 * @param {string} props.accentColor - CSS color for the left border accent
 * @param {string} props.insight - One-sentence "what's interesting" description
 * @param {string} props.users - Formatted user count string e.g. "10,000"
 * @param {string} props.metricType - e.g. "Conversion Rate"
 * @param {'NEEDS_REVIEW'|'SIGNIFICANT'|'NOT_SIGNIFICANT'|'INVALID'} props.verdict
 */
export default function SampleCard({ slug, title, accentColor, insight, users, metricType, verdict }) {
  const vs = VERDICT_STYLES[verdict] ?? VERDICT_STYLES.NOT_SIGNIFICANT

  return (
    <Link to={`/demo/${slug}`} className="block group" style={{ textDecoration: 'none' }}>
      <div
        className="relative rounded-lg border border-subtle h-full flex flex-col overflow-hidden
                   transition-all duration-200 group-hover:-translate-y-0.5"
        style={{
          backgroundColor: 'var(--color-bg-card)',
          borderLeftWidth: 3,
          borderLeftColor: accentColor,
          boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = 'var(--color-border-active)'
          e.currentTarget.style.borderLeftColor = accentColor
          e.currentTarget.style.boxShadow = `0 8px 24px rgba(0,0,0,0.5), 0 0 0 1px rgba(42,74,107,0.6)`
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = 'var(--color-border-subtle)'
          e.currentTarget.style.borderLeftColor = accentColor
          e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.4)'
        }}
      >
        {/* DEMO badge */}
        <div className="absolute top-3 right-3">
          <span
            className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full"
            style={{
              color: 'var(--color-accent-amber)',
              backgroundColor: 'rgba(245,158,11,0.1)',
              border: '1px solid rgba(245,158,11,0.3)',
            }}
          >
            <Sparkles size={8} />
            Demo
          </span>
        </div>

        {/* Card body */}
        <div className="p-5 flex-1 flex flex-col">
          <h3
            className="font-display font-bold text-[15px] leading-snug mb-3 pr-14 transition-colors group-hover:text-data"
            style={{ color: 'var(--color-text-primary)' }}
          >
            {title}
          </h3>

          <p
            className="text-[13px] leading-relaxed flex-1"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {insight}
          </p>
        </div>

        {/* Stat pills */}
        <div
          className="px-5 pb-5 pt-4 flex items-center flex-wrap gap-2 border-t"
          style={{ borderColor: 'var(--color-border-subtle)' }}
        >
          {/* Users */}
          <span
            className="text-[11px] px-2 py-0.5 rounded-full"
            style={{
              color: 'var(--color-text-muted)',
              backgroundColor: 'rgba(71,85,105,0.15)',
              border: '1px solid rgba(71,85,105,0.3)',
            }}
          >
            {users} users
          </span>

          {/* Metric type */}
          <span
            className="text-[11px] px-2 py-0.5 rounded-full"
            style={{
              color: 'var(--color-text-muted)',
              backgroundColor: 'rgba(71,85,105,0.15)',
              border: '1px solid rgba(71,85,105,0.3)',
            }}
          >
            {metricType}
          </span>

          {/* Verdict */}
          <span
            className="text-[11px] px-2 py-0.5 rounded-full font-medium ml-auto"
            style={{
              color: vs.color,
              backgroundColor: vs.bg,
              border: `1px solid ${vs.border}`,
            }}
          >
            {vs.label}
          </span>
        </div>
      </div>
    </Link>
  )
}
