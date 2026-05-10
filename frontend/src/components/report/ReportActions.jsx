import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Copy, Check, Printer } from 'lucide-react'
import { formatDistanceToNow, parseISO, isValid } from 'date-fns'
import Button from '../ui/Button'

/**
 * Sticky action bar shown at the bottom of the report document.
 * Adapts to mobile by hiding text labels when space is tight.
 *
 * @param {Object} props
 * @param {string} props.experimentId
 * @param {string|null} props.generatedAt  - ISO timestamp
 * @param {string|null} props.markdown     - Full markdown to copy
 */
export default function ReportActions({ experimentId, generatedAt, markdown }) {
  const [copied, setCopied] = useState(false)

  let timeAgo = null
  if (generatedAt) {
    try {
      const d = parseISO(generatedAt)
      if (isValid(d)) timeAgo = formatDistanceToNow(d, { addSuffix: true })
    } catch {
      // ignore
    }
  }

  function handleCopy() {
    const text = markdown ?? document.querySelector('[data-report-content]')?.innerText ?? ''
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    })
  }

  function handlePrint() {
    window.print()
  }

  return (
    <div
      className="sticky bottom-0 z-20 border-t print:hidden"
      style={{
        backgroundColor: 'var(--color-bg-deep)',
        borderColor: 'var(--color-border-subtle)',
      }}
    >
      <div className="max-w-[720px] mx-auto px-4 py-3 flex items-center justify-between gap-4">
        {/* Left: back link */}
        <Link to={`/experiments/${experimentId}`}>
          <Button variant="ghost" size="sm">
            <ArrowLeft size={13} />
            <span className="hidden sm:inline">Back to Results</span>
          </Button>
        </Link>

        {/* Center: metadata */}
        {timeAgo && (
          <span
            className="text-xs hidden md:block"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Generated {timeAgo}
          </span>
        )}

        {/* Right: actions */}
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={handleCopy}>
            {copied ? (
              <Check size={13} style={{ color: 'var(--color-accent-green)' }} />
            ) : (
              <Copy size={13} />
            )}
            <span className="hidden sm:inline">{copied ? 'Copied!' : 'Copy to Clipboard'}</span>
          </Button>

          <Button variant="secondary" size="sm" onClick={handlePrint}>
            <Printer size={13} />
            <span className="hidden sm:inline">Download PDF</span>
          </Button>
        </div>
      </div>
    </div>
  )
}
