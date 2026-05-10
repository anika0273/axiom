import { ServerCrash, RefreshCw } from 'lucide-react'
import Button from '../ui/Button'

/**
 * Shown for unexpected server errors (5xx).
 *
 * @param {Object} props
 * @param {string} [props.code] - Error code to display (e.g. 'INTERNAL_ERROR')
 * @param {string} [props.message]
 * @param {() => void} [props.onRetry]
 * @param {string} [props.className]
 */
export default function APIError({ code, message, onRetry, className = '' }) {
  return (
    <div
      className={`flex flex-col items-center justify-center py-24 text-center px-6 ${className}`}
    >
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center mb-5"
        style={{ backgroundColor: 'rgba(239,68,68,0.1)' }}
      >
        <ServerCrash size={26} style={{ color: 'var(--color-accent-red)' }} />
      </div>

      <h2
        className="font-display font-bold text-lg mb-2"
        style={{ color: 'var(--color-text-primary)' }}
      >
        Something went wrong on our end
      </h2>
      <p
        className="text-sm mb-3 max-w-xs leading-relaxed"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        {message ?? 'An unexpected server error occurred. Our team has been notified.'}
      </p>

      {code && (
        <p
          className="font-mono text-[11px] mb-5 px-2 py-0.5 rounded"
          style={{
            color: 'var(--color-text-muted)',
            backgroundColor: 'var(--color-bg-elevated)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          {code}
        </p>
      )}

      <Button variant="secondary" size="sm" onClick={onRetry}>
        <RefreshCw size={13} />
        Try again
      </Button>
    </div>
  )
}
