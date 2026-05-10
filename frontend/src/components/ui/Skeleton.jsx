import { clsx } from 'clsx'

const shimmerStyle = {
  background:
    'linear-gradient(90deg, var(--color-bg-card) 25%, var(--color-bg-elevated) 50%, var(--color-bg-card) 75%)',
  backgroundSize: '200% 100%',
}

/**
 * Shimmer placeholder that matches the shape of loading content.
 * @param {Object} props
 * @param {'text'|'card'|'chart'|'chart-axes'|'table-row'|'list-row'|'paragraph'|'report-header'} [props.variant='text']
 * @param {string} [props.className]
 */
export default function Skeleton({ variant = 'text', className }) {
  if (variant === 'card') {
    return (
      <div
        className={clsx('animate-shimmer rounded-lg h-32', className)}
        style={shimmerStyle}
      />
    )
  }

  if (variant === 'chart') {
    return (
      <div
        className={clsx('animate-shimmer rounded-lg h-48', className)}
        style={shimmerStyle}
      />
    )
  }

  // Chart with axis lines — more realistic than plain rect
  if (variant === 'chart-axes') {
    return (
      <div
        className={clsx('rounded-lg h-48 relative overflow-hidden', className)}
        style={{ backgroundColor: 'var(--color-bg-card)', border: '1px solid var(--color-border-subtle)' }}
      >
        {/* Shimmer overlay */}
        <div className="absolute inset-0 animate-shimmer" style={shimmerStyle} />
        {/* Y-axis line */}
        <div
          className="absolute left-10 top-4 bottom-8 w-px"
          style={{ backgroundColor: 'var(--color-border-subtle)' }}
        />
        {/* X-axis line */}
        <div
          className="absolute left-10 right-4 bottom-8 h-px"
          style={{ backgroundColor: 'var(--color-border-subtle)' }}
        />
        {/* Y-axis tick marks */}
        {[20, 40, 60].map((pct) => (
          <div
            key={pct}
            className="absolute left-8 w-2 h-px"
            style={{
              bottom: `calc(8px + ${pct}%)`,
              backgroundColor: 'var(--color-border-subtle)',
            }}
          />
        ))}
      </div>
    )
  }

  if (variant === 'table-row') {
    return (
      <div className={clsx('flex gap-4 py-3 border-b border-subtle', className)}>
        <div className="animate-shimmer rounded h-4 w-1/3" style={shimmerStyle} />
        <div className="animate-shimmer rounded h-4 w-1/4" style={shimmerStyle} />
        <div className="animate-shimmer rounded h-4 w-1/5" style={shimmerStyle} />
        <div className="animate-shimmer rounded h-4 flex-1" style={shimmerStyle} />
      </div>
    )
  }

  // ExperimentList card row — status dot + name + meta + right action
  if (variant === 'list-row') {
    return (
      <div
        className={clsx('flex items-center gap-4 px-5 py-4 border-b border-subtle last:border-0', className)}
      >
        {/* Status dot */}
        <div
          className="w-2 h-2 rounded-full flex-shrink-0"
          style={{ backgroundColor: 'var(--color-border-active)' }}
        />
        {/* Name + description */}
        <div className="flex-1 min-w-0 space-y-2">
          <div className="animate-shimmer rounded h-4 w-1/2" style={shimmerStyle} />
          <div className="animate-shimmer rounded h-3 w-1/3" style={shimmerStyle} />
        </div>
        {/* Center pills (hidden on small screens) */}
        <div className="hidden md:flex items-center gap-2 flex-shrink-0">
          <div className="animate-shimmer rounded-full h-5 w-28" style={shimmerStyle} />
          <div className="animate-shimmer rounded h-5 w-16" style={shimmerStyle} />
        </div>
        {/* Right meta */}
        <div className="flex-shrink-0 space-y-1.5 w-28">
          <div className="animate-shimmer rounded h-4 w-full" style={shimmerStyle} />
          <div className="animate-shimmer rounded h-3 w-2/3" style={shimmerStyle} />
        </div>
      </div>
    )
  }

  // Paragraph block — 3 lines of varying width
  if (variant === 'paragraph') {
    return (
      <div className={clsx('space-y-2', className)}>
        <div className="animate-shimmer rounded h-4 w-full" style={shimmerStyle} />
        <div className="animate-shimmer rounded h-4 w-5/6" style={shimmerStyle} />
        <div className="animate-shimmer rounded h-4 w-3/4" style={shimmerStyle} />
      </div>
    )
  }

  // Report document header — title + date + meta
  if (variant === 'report-header') {
    return (
      <div className={clsx('space-y-3 mb-8', className)}>
        <div className="animate-shimmer rounded h-7 w-2/3" style={shimmerStyle} />
        <div className="animate-shimmer rounded h-4 w-1/3" style={shimmerStyle} />
        <div className="flex gap-2 pt-1">
          <div className="animate-shimmer rounded-full h-6 w-24" style={shimmerStyle} />
          <div className="animate-shimmer rounded-full h-6 w-20" style={shimmerStyle} />
        </div>
      </div>
    )
  }

  // default: single text line
  return (
    <div
      className={clsx('animate-shimmer rounded h-4', className)}
      style={shimmerStyle}
    />
  )
}
