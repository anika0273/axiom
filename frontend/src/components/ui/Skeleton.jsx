import { clsx } from 'clsx'

const shimmerStyle = {
  background:
    'linear-gradient(90deg, var(--color-bg-card) 25%, var(--color-bg-elevated) 50%, var(--color-bg-card) 75%)',
  backgroundSize: '200% 100%',
}

/**
 * Shimmer placeholder that matches the shape of loading content.
 * @param {Object} props
 * @param {'text'|'card'|'chart'|'table-row'} [props.variant='text']
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

  // default: text line
  return (
    <div
      className={clsx('animate-shimmer rounded h-4', className)}
      style={shimmerStyle}
    />
  )
}
