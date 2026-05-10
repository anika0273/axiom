import { Clock, RefreshCw } from 'lucide-react'
import Button from '../ui/Button'

/**
 * Shown when a request has been loading for longer than expected (≥ 10 s).
 *
 * @param {Object} props
 * @param {() => void} [props.onRetry]
 * @param {string} [props.className]
 */
export default function TimeoutError({ onRetry, className = '' }) {
  return (
    <div
      className={`flex flex-col items-center justify-center py-24 text-center px-6 ${className}`}
    >
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center mb-5"
        style={{ backgroundColor: 'rgba(245,158,11,0.1)' }}
      >
        <Clock size={26} style={{ color: 'var(--color-accent-amber)' }} />
      </div>

      <h2
        className="font-display font-bold text-lg mb-2"
        style={{ color: 'var(--color-text-primary)' }}
      >
        Taking longer than usual
      </h2>
      <p
        className="text-sm mb-6 max-w-xs leading-relaxed"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        The server is taking too long to respond. This may be a temporary issue — try refreshing the page.
      </p>

      <Button variant="secondary" size="sm" onClick={onRetry ?? (() => window.location.reload())}>
        <RefreshCw size={13} />
        Refresh
      </Button>
    </div>
  )
}
