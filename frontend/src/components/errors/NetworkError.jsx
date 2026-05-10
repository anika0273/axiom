import { useEffect, useState } from 'react'
import { WifiOff, RefreshCw } from 'lucide-react'
import Button from '../ui/Button'

/**
 * Full-page error state for network / offline failures.
 * Auto-retries when the browser comes back online.
 *
 * @param {Object} props
 * @param {() => void} [props.onRetry]
 * @param {string} [props.className]
 */
export default function NetworkError({ onRetry, className = '' }) {
  const [online, setOnline] = useState(navigator.onLine)

  useEffect(() => {
    const handleOnline = () => {
      setOnline(true)
      onRetry?.()
    }
    const handleOffline = () => setOnline(false)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [onRetry])

  return (
    <div
      className={`flex flex-col items-center justify-center py-24 text-center px-6 ${className}`}
    >
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center mb-5"
        style={{ backgroundColor: 'rgba(71,85,105,0.15)' }}
      >
        <WifiOff size={26} style={{ color: 'var(--color-text-muted)' }} />
      </div>

      <h2
        className="font-display font-bold text-lg mb-2"
        style={{ color: 'var(--color-text-primary)' }}
      >
        You appear to be offline
      </h2>
      <p
        className="text-sm mb-6 max-w-xs leading-relaxed"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        {online
          ? 'Connection restored. Retrying…'
          : 'Check your internet connection and try again. The page will reload automatically when you reconnect.'}
      </p>

      <Button
        variant="secondary"
        size="sm"
        onClick={onRetry}
        disabled={!online}
      >
        <RefreshCw size={13} />
        Retry
      </Button>
    </div>
  )
}
