import { Check, X, Clock, Search, HelpCircle } from 'lucide-react'

const CONFIGS = {
  SHIP: {
    Icon: Check,
    label: 'Ship',
    bg: 'var(--color-accent-green)',
    text: '#ffffff',
    glow: 'rgba(16,185,129,0.35)',
    subtleBg: 'rgba(16,185,129,0.1)',
    subtleText: 'var(--color-accent-green)',
  },
  DO_NOT_SHIP: {
    Icon: X,
    label: 'Do Not Ship',
    bg: 'var(--color-accent-red)',
    text: '#ffffff',
    glow: 'rgba(239,68,68,0.35)',
    subtleBg: 'rgba(239,68,68,0.1)',
    subtleText: 'var(--color-accent-red)',
  },
  EXTEND: {
    Icon: Clock,
    label: 'Extend Test',
    bg: 'var(--color-accent-amber)',
    text: '#1a1200',
    glow: 'rgba(245,158,11,0.35)',
    subtleBg: 'rgba(245,158,11,0.1)',
    subtleText: 'var(--color-accent-amber)',
  },
  INVESTIGATE: {
    Icon: Search,
    label: 'Investigate',
    bg: 'var(--color-accent-blue)',
    text: '#ffffff',
    glow: 'rgba(59,130,246,0.35)',
    subtleBg: 'rgba(59,130,246,0.1)',
    subtleText: 'var(--color-accent-blue)',
  },
  NEEDS_REVIEW: {
    Icon: Search,
    label: 'Needs Review',
    bg: 'var(--color-accent-blue)',
    text: '#ffffff',
    glow: 'rgba(59,130,246,0.35)',
    subtleBg: 'rgba(59,130,246,0.1)',
    subtleText: 'var(--color-accent-blue)',
  },
}

function normalise(raw) {
  if (!raw) return 'INVESTIGATE'
  const upper = raw.toUpperCase().replace(/[\s-]+/g, '_')
  if (upper.includes('NOT_SHIP') || upper.includes('NO_SHIP') || upper === 'DO_NOT_SHIP') return 'DO_NOT_SHIP'
  if (upper === 'SHIP') return 'SHIP'
  if (upper === 'EXTEND') return 'EXTEND'
  if (upper.includes('REVIEW') || upper.includes('NEEDS')) return 'NEEDS_REVIEW'
  return 'INVESTIGATE'
}

/** Confidence dot indicator (e.g. ●●○ Medium Confidence) */
function ConfidenceDots({ level }) {
  const map = {
    HIGH: { dots: [true, true, true], label: 'High Confidence' },
    MEDIUM: { dots: [true, true, false], label: 'Medium Confidence' },
    LOW: { dots: [true, false, false], label: 'Low Confidence' },
  }
  const cfg = map[level?.toUpperCase()] ?? map.MEDIUM
  return (
    <div className="flex items-center gap-2 justify-center mt-4">
      <span className="flex items-center gap-0.5">
        {cfg.dots.map((filled, i) => (
          <span
            key={i}
            className="inline-block w-2 h-2 rounded-full"
            style={{
              backgroundColor: filled
                ? 'var(--color-text-secondary)'
                : 'var(--color-border-subtle)',
            }}
          />
        ))}
      </span>
      <span
        className="text-xs"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {cfg.label}
      </span>
    </div>
  )
}

/**
 * Large recommendation pill badge with confidence indicator.
 * @param {Object} props
 * @param {string|null} props.recommendation  - "SHIP", "DO_NOT_SHIP", "EXTEND", "INVESTIGATE", etc.
 * @param {string|null} props.confidence      - "HIGH", "MEDIUM", "LOW"
 * @param {string|null} props.reasoning       - tooltip / subtitle text
 */
export default function RecommendationBadge({ recommendation, confidence, reasoning }) {
  const key = normalise(recommendation)
  const cfg = CONFIGS[key] ?? CONFIGS.INVESTIGATE
  const { Icon } = cfg

  return (
    <div className="flex flex-col items-center mb-10 print:mb-6">
      <div
        className="inline-flex items-center gap-3 px-8 py-4 rounded-full font-display font-bold"
        style={{
          fontSize: 20,
          backgroundColor: cfg.bg,
          color: cfg.text,
          boxShadow: `0 0 32px ${cfg.glow}`,
        }}
      >
        <Icon size={20} strokeWidth={2.5} />
        {cfg.label}
      </div>

      {confidence && <ConfidenceDots level={confidence} />}

      {reasoning && (
        <p
          className="mt-3 text-xs text-center max-w-sm leading-relaxed"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {reasoning}
        </p>
      )}
    </div>
  )
}

// Export the normalise helper so ReportSection can use the same colour mapping
export { normalise, CONFIGS }
