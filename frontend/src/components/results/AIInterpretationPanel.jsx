import { useState, useRef, useEffect } from 'react'
import { Zap, ChevronDown, Copy, Check, FileText } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useStreamingInterpretation } from '../../hooks/useStreamingInterpretation'
import Button from '../ui/Button'

const FALLBACK_TEXT =
  'AI interpretation is currently unavailable. View the raw statistics above to evaluate this experiment. The key metrics — p-value, confidence interval, and lift — are shown in the sections above. Consult your analytics team for a plain-language summary.'

function buildFallbackFromResult(result) {
  if (!result) return FALLBACK_TEXT
  const liftStr =
    result.liftPct != null
      ? `${result.liftPct >= 0 ? '+' : ''}${result.liftPct.toFixed(1)}%`
      : null
  const pStr = result.pValue != null ? result.pValue.toFixed(4) : null
  const sigVerdict = result.isSignificant
    ? 'statistically significant'
    : 'not statistically significant'
  const rec = result.recommendation ? ` Recommendation: ${result.recommendation}.` : ''
  const segNote = result.segments ? ' Segment analysis is available above.' : ''
  const statsClause =
    liftStr && pStr
      ? ` The experiment shows a relative lift of ${liftStr} (p = ${pStr}), which is ${sigVerdict}.`
      : ` The result is ${sigVerdict}.`
  return (
    `AI interpretation is currently unavailable. Based on the raw statistics:${statsClause}${rec}${segNote} ` +
    `View the full metrics above for detailed results.`
  )
}

function Cursor() {
  return (
    <span
      className="inline-block w-0.5 h-4 ml-0.5 align-text-bottom animate-pulse"
      style={{ backgroundColor: 'var(--color-accent-blue)' }}
    />
  )
}

/**
 * Collapsible AI interpretation panel with SSE streaming.
 * @param {Object} props
 * @param {string} props.experimentId
 * @param {string} [props.experimentName]
 * @param {Object|null} [props.result] - live result object for dynamic fallback text
 */
export default function AIInterpretationPanel({ experimentId, experimentName, result }) {
  const [expanded, setExpanded] = useState(false)
  const [started, setStarted] = useState(false)
  const [copied, setCopied] = useState(false)
  const { text, streaming, error, startStream } = useStreamingInterpretation(experimentId)

  const handleInterpret = () => {
    setStarted(true)
    startStream()
  }

  const isFallback = !!(error || (!streaming && started && !text))
  const fallbackContent = buildFallbackFromResult(result)

  const handleCopy = () => {
    const content = text || fallbackContent
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const displayText = text || (isFallback ? fallbackContent : '')
  const showSkeleton = streaming && !text
  const showText = displayText.length > 0

  return (
    <div
      className="rounded-xl border print:hidden"
      id="interpretation"
      style={{
        borderColor: expanded
          ? 'rgba(59,130,246,0.3)'
          : 'var(--color-border-subtle)',
        backgroundColor: 'var(--color-bg-card)',
        borderLeftWidth: expanded ? 3 : 1,
        borderLeftColor: expanded ? 'var(--color-accent-blue)' : 'var(--color-border-subtle)',
        transition: 'border-color 200ms',
      }}
    >
      {/* Header — always visible */}
      <button
        className="w-full flex items-center justify-between px-6 py-4 text-left"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-2.5">
          <Zap
            size={16}
            style={{ color: 'var(--color-accent-blue)' }}
            strokeWidth={2.5}
          />
          <span
            className="font-display font-bold text-base"
            style={{ color: 'var(--color-text-primary)' }}
          >
            AI Interpretation
          </span>
          <span
            className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full border font-medium"
            style={{
              color: 'var(--color-accent-blue)',
              borderColor: 'rgba(59,130,246,0.3)',
              backgroundColor: 'rgba(59,130,246,0.08)',
            }}
          >
            Powered by Claude
          </span>
        </div>
        <ChevronDown
          size={16}
          style={{
            color: 'var(--color-text-muted)',
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 200ms',
          }}
        />
      </button>

      {/* Collapsible body */}
      {expanded && (
        <div className="px-6 pb-6">
          {/* Prompt to start */}
          {!started && (
            <div className="text-center py-8">
              <p
                className="text-sm mb-4"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Get a plain-English explanation of these results
              </p>
              <Button onClick={handleInterpret}>
                Interpret Results →
              </Button>
            </div>
          )}

          {/* Skeleton while streaming with no text yet */}
          {showSkeleton && (
            <div className="space-y-3 py-4">
              {[100, 80, 92].map((w, i) => (
                <div
                  key={i}
                  className="h-4 rounded animate-pulse"
                  style={{
                    width: `${w}%`,
                    backgroundColor: 'var(--color-bg-elevated)',
                  }}
                />
              ))}
              <p
                className="text-xs mt-2"
                style={{ color: 'var(--color-text-muted)' }}
              >
                Analyzing results…
              </p>
            </div>
          )}

          {/* Interpretation text */}
          {showText && (
            <div>
              <p
                className="text-sm leading-relaxed whitespace-pre-wrap"
                style={{ color: 'var(--color-text-primary)' }}
              >
                {displayText}
                {streaming && <Cursor />}
              </p>

              {/* Fallback badge */}
              {isFallback && (
                <span
                  className="inline-flex items-center gap-1 mt-2 text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full border"
                  style={{
                    color: 'var(--color-text-muted)',
                    borderColor: 'var(--color-border-subtle)',
                  }}
                >
                  Auto-generated · AI unavailable
                </span>
              )}

              {/* Actions (shown after streaming completes) */}
              {!streaming && (
                <div className="flex items-center gap-3 mt-5 pt-4 border-t border-subtle">
                  <Link to={`/experiments/${experimentId}/report`}>
                    <Button variant="secondary" size="sm">
                      <FileText size={13} />
                      Generate Stakeholder Report →
                    </Button>
                  </Link>
                  <Button variant="ghost" size="sm" onClick={handleCopy}>
                    {copied ? (
                      <Check size={13} style={{ color: 'var(--color-accent-green)' }} />
                    ) : (
                      <Copy size={13} />
                    )}
                    {copied ? 'Copied!' : 'Copy to Clipboard'}
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
