import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ChevronDown } from 'lucide-react'
import { normalise, CONFIGS } from './RecommendationBadge'

// ---------------------------------------------------------------------------
// Markdown component overrides — styled for document readability
// ---------------------------------------------------------------------------

const mdComponents = {
  p({ children }) {
    return (
      <p
        className="mb-4 last:mb-0"
        style={{
          color: 'var(--color-text-secondary)',
          fontSize: 15,
          lineHeight: 1.75,
        }}
      >
        {children}
      </p>
    )
  },
  h2({ children }) {
    return (
      <h3
        className="font-display font-semibold text-xs uppercase tracking-widest mt-6 mb-2"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {children}
      </h3>
    )
  },
  h3({ children }) {
    return (
      <h4
        className="font-display font-semibold text-sm mt-4 mb-1"
        style={{ color: 'var(--color-text-primary)' }}
      >
        {children}
      </h4>
    )
  },
  strong({ children }) {
    return (
      <span
        className="font-semibold"
        style={{ color: 'var(--color-text-primary)' }}
      >
        {children}
      </span>
    )
  },
  code({ inline, children }) {
    if (inline) {
      return (
        <code
          className="font-mono text-sm px-1.5 py-0.5 rounded"
          style={{
            backgroundColor: 'var(--color-bg-elevated)',
            color: 'var(--color-accent-blue)',
          }}
        >
          {children}
        </code>
      )
    }
    return (
      <code
        className="block font-mono text-sm p-3 rounded-lg my-3 overflow-x-auto"
        style={{
          backgroundColor: 'var(--color-bg-elevated)',
          color: 'var(--color-text-secondary)',
        }}
      >
        {children}
      </code>
    )
  },
  ul({ children }) {
    return <ul className="list-disc ml-5 mb-4 space-y-1">{children}</ul>
  },
  ol({ children }) {
    return <ol className="list-decimal ml-5 mb-4 space-y-1">{children}</ol>
  },
  li({ children }) {
    return (
      <li style={{ color: 'var(--color-text-secondary)', fontSize: 15, lineHeight: 1.7 }}>
        {children}
      </li>
    )
  },
  table({ children }) {
    return (
      <div className="overflow-x-auto my-4">
        <table
          className="w-full text-sm border-collapse"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          {children}
        </table>
      </div>
    )
  },
  thead({ children }) {
    return (
      <thead style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
        {children}
      </thead>
    )
  },
  th({ children }) {
    return (
      <th
        className="py-2 px-3 text-left text-xs font-semibold uppercase tracking-wider"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {children}
      </th>
    )
  },
  tr({ children, ...props }) {
    return (
      <tr
        className="border-b border-subtle even:bg-elevated"
        {...props}
      >
        {children}
      </tr>
    )
  },
  td({ children }) {
    return (
      <td className="py-2 px-3 font-mono text-xs">{children}</td>
    )
  },
}

// Lead text wrapper for Executive Summary section
const leadMdComponents = {
  ...mdComponents,
  p({ children }) {
    return (
      <p
        className="mb-4 last:mb-0"
        style={{
          color: 'var(--color-text-primary)',
          fontSize: 18,
          lineHeight: 1.75,
        }}
      >
        {children}
      </p>
    )
  },
}

// ---------------------------------------------------------------------------
// Revenue callout detector — looks for dollar amounts / revenue phrases
// ---------------------------------------------------------------------------

function extractRevenueCallout(content) {
  // Look for lines with $ amounts or "revenue impact" phrases
  const match = content?.match(/\$[\d,]+(?:\.\d+)?(?:\s*(?:million|M|K|thousand|billion|B))?(?:[^\n.]*(?:impact|uplift|revenue|GMV|value)[^\n.]*)?/i)
  return match ? match[0].trim() : null
}

// ---------------------------------------------------------------------------
// Section components by type
// ---------------------------------------------------------------------------

function SectionHeader({ number, title }) {
  return (
    <div className="mb-4">
      <div className="flex items-baseline gap-3 mb-2">
        <span
          className="font-mono text-xs font-medium tabular-nums"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {String(number).padStart(2, '0')}
        </span>
        <span
          className="text-[10px] uppercase tracking-[0.15em] font-semibold"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {title}
        </span>
      </div>
      <div
        className="h-px w-full"
        style={{ backgroundColor: 'var(--color-border-subtle)' }}
      />
    </div>
  )
}

function ExecutiveSummarySection({ number, title, content }) {
  return (
    <div className="mb-10">
      <SectionHeader number={number} title={title} />
      <ReactMarkdown components={leadMdComponents} remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

function BusinessImpactSection({ number, title, content }) {
  const callout = extractRevenueCallout(content)

  return (
    <div className="mb-10">
      <SectionHeader number={number} title={title} />
      {callout && (
        <div
          className="mb-4 px-4 py-3 rounded-lg"
          style={{
            borderLeft: '3px solid var(--color-accent-blue)',
            backgroundColor: 'rgba(59,130,246,0.06)',
          }}
        >
          <p
            className="font-mono text-sm font-medium"
            style={{ color: 'var(--color-accent-blue)' }}
          >
            {callout}
          </p>
          <p
            className="text-xs mt-1"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Estimated business impact
          </p>
        </div>
      )}
      <ReactMarkdown components={mdComponents} remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

function ResultsSection({ number, title, content }) {
  // Wrap percentage values in coloured inline badges
  const augmentedContent = content?.replace(
    /([+-]?\d+\.?\d*%(?:\s+(?:relative|lift|improvement|decline|uplift))?)/gi,
    (match) => {
      const isNeg = match.startsWith('-')
      const tag = isNeg ? '🔴' : '🟢'
      return `\`${match}\``
    },
  )

  return (
    <div className="mb-10">
      <SectionHeader number={number} title={title} />
      <ReactMarkdown components={mdComponents} remarkPlugins={[remarkGfm]}>
        {augmentedContent || content}
      </ReactMarkdown>
    </div>
  )
}

function RecommendationSection({ number, title, content, recommendation }) {
  const key = normalise(recommendation)
  const cfg = CONFIGS[key] ?? CONFIGS.INVESTIGATE

  return (
    <div className="mb-10">
      <SectionHeader number={number} title={title} />
      <div
        className="pl-4 py-1"
        style={{ borderLeft: `3px solid ${cfg.bg}` }}
      >
        <ReactMarkdown
          components={{
            ...mdComponents,
            p({ children }) {
              return (
                <p
                  className="mb-4 last:mb-0 text-base"
                  style={{ color: 'var(--color-text-primary)', lineHeight: 1.75 }}
                >
                  {children}
                </p>
              )
            },
            strong({ children }) {
              return (
                <strong
                  className="font-bold"
                  style={{ color: cfg.bg }}
                >
                  {children}
                </strong>
              )
            },
          }}
          remarkPlugins={[remarkGfm]}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  )
}

function TechnicalAppendixSection({ number, title, content }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="mb-10">
      <SectionHeader number={number} title={title} />
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-2 text-sm mb-4 transition-colors"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        <ChevronDown
          size={15}
          style={{
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 200ms',
            color: 'var(--color-text-muted)',
          }}
        />
        {expanded ? 'Hide Technical Details' : 'Show Technical Details'}
      </button>
      {expanded && (
        <ReactMarkdown components={mdComponents} remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      )}
    </div>
  )
}

function StandardSection({ number, title, content }) {
  return (
    <div className="mb-10">
      <SectionHeader number={number} title={title} />
      <ReactMarkdown components={mdComponents} remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Exported component — picks the right variant by section number
// ---------------------------------------------------------------------------

/**
 * Renders a single report section with section-appropriate visual treatment.
 * @param {Object} props
 * @param {number} props.number        - 1-based section number
 * @param {string} props.title         - Section title
 * @param {string} props.content       - Markdown/plain text content
 * @param {string|null} props.recommendation - Overall report recommendation (for Section 7 colouring)
 */
export default function ReportSection({ number, title, content, recommendation }) {
  if (!content) return null

  if (number === 1) {
    return <ExecutiveSummarySection number={number} title={title} content={content} />
  }
  if (number === 2) {
    return <BusinessImpactSection number={number} title={title} content={content} />
  }
  if (number === 4) {
    return <ResultsSection number={number} title={title} content={content} />
  }
  if (number === 7) {
    return (
      <RecommendationSection
        number={number}
        title={title}
        content={content}
        recommendation={recommendation}
      />
    )
  }
  if (number === 8) {
    return <TechnicalAppendixSection number={number} title={title} content={content} />
  }
  return <StandardSection number={number} title={title} content={content} />
}
