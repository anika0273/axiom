import { Link } from 'react-router-dom'
import { SearchX, ArrowLeft } from 'lucide-react'
import Button from '../ui/Button'

/**
 * Shown when a resource returns 404.
 *
 * @param {Object} props
 * @param {string} [props.resourceName] - e.g. "experiment"
 * @param {string} [props.backHref] - Where the back link goes (default: /experiments)
 * @param {string} [props.backLabel] - Back link label
 * @param {string} [props.className]
 */
export default function NotFoundError({
  resourceName = 'resource',
  backHref = '/experiments',
  backLabel = 'Back to experiments',
  className = '',
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center py-24 text-center px-6 ${className}`}
    >
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center mb-5"
        style={{ backgroundColor: 'rgba(71,85,105,0.15)' }}
      >
        <SearchX size={26} style={{ color: 'var(--color-text-muted)' }} />
      </div>

      <p
        className="font-mono text-4xl font-medium mb-3"
        style={{ color: 'var(--color-text-muted)' }}
      >
        404
      </p>
      <h2
        className="font-display font-bold text-lg mb-2"
        style={{ color: 'var(--color-text-primary)' }}
      >
        This {resourceName} doesn't exist
      </h2>
      <p
        className="text-sm mb-8 max-w-xs leading-relaxed"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        It may have been deleted, or the link might be wrong.
      </p>

      <Link to={backHref}>
        <Button variant="secondary" size="sm">
          <ArrowLeft size={13} />
          {backLabel}
        </Button>
      </Link>
    </div>
  )
}
