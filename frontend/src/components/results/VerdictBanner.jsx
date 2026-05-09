import { CheckCircle2, MinusCircle, AlertTriangle } from 'lucide-react'
import Badge from '../ui/Badge'

const CONFIGS = {
  SIGNIFICANT: {
    bg: 'linear-gradient(135deg, rgba(16,185,129,0.15) 0%, transparent 65%)',
    borderColor: 'rgba(16,185,129,0.25)',
    verdictColor: 'var(--color-accent-green)',
    Icon: CheckCircle2,
  },
  NOT_SIGNIFICANT: {
    bg: 'var(--color-bg-card)',
    borderColor: 'var(--color-border-subtle)',
    verdictColor: 'var(--color-text-secondary)',
    Icon: MinusCircle,
  },
  INVALID: {
    bg: 'linear-gradient(135deg, rgba(239,68,68,0.12) 0%, transparent 65%)',
    borderColor: 'rgba(239,68,68,0.25)',
    verdictColor: 'var(--color-accent-red)',
    Icon: AlertTriangle,
  },
}

function liftColor(liftPct, isSignificant) {
  if (liftPct < 0) return 'var(--color-accent-red)'
  if (isSignificant) return 'var(--color-accent-green)'
  return 'var(--color-accent-amber)'
}

function fmtPValue(p) {
  if (p === null || p === undefined) return null
  if (p === 0 || p < 0.001) return 'p < 0.001'
  return `p = ${p.toFixed(3)}`
}

function fmtCI(low, high) {
  if (low == null || high == null) return null
  const fmt = (v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
  return `95% CI [${fmt(low)}, ${fmt(high)}]`
}

/**
 * Full-width 120px verdict banner.
 * @param {Object} props
 * @param {'SIGNIFICANT'|'NOT_SIGNIFICANT'|'INVALID'} props.verdict
 * @param {number|null} props.pValue
 * @param {number|null} props.ciLow  - absolute pp, e.g. 10.8
 * @param {number|null} props.ciHigh - absolute pp, e.g. 13.7
 * @param {number} props.liftPct     - relative lift %
 * @param {'completed'|'running'|'draft'} props.status
 */
export default function VerdictBanner({ verdict, pValue, ciLow, ciHigh, liftPct, status }) {
  const cfg = CONFIGS[verdict] ?? CONFIGS.NOT_SIGNIFICANT
  const Icon = cfg.Icon
  const liftStr = `${liftPct >= 0 ? '+' : ''}${liftPct.toFixed(1)}%`
  const pStr = fmtPValue(pValue)
  const ciStr = fmtCI(ciLow, ciHigh)
  const subline = [pStr, ciStr].filter(Boolean).join(' · ')
  const color = liftColor(liftPct, verdict === 'SIGNIFICANT')
  const badgeVariant = status === 'running' ? 'running' : status === 'completed' ? 'completed' : 'warning'

  return (
    <div
      className="w-full rounded-xl border mb-6 px-6 flex items-center justify-between gap-6 print:border print:bg-white"
      style={{
        minHeight: 120,
        background: cfg.bg,
        borderColor: cfg.borderColor,
      }}
    >
      {/* Left: verdict label + stat line */}
      <div className="flex items-center gap-4 min-w-0">
        <Icon size={28} style={{ color: cfg.verdictColor, flexShrink: 0 }} strokeWidth={2} />
        <div className="min-w-0">
          <p
            className="font-display font-bold tracking-widest uppercase leading-none"
            style={{ fontSize: 32, color: cfg.verdictColor }}
          >
            {verdict.replace('_', ' ')}
          </p>
          {subline && (
            <p
              className="font-mono text-sm mt-2"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              {subline}
            </p>
          )}
        </div>
      </div>

      {/* Center: lift */}
      <div className="text-center flex-shrink-0">
        <p
          className="font-mono font-medium leading-none"
          style={{ fontSize: 48, color }}
        >
          {liftStr}
        </p>
        <p
          className="text-xs uppercase tracking-widest mt-1.5"
          style={{ color: 'var(--color-text-muted)' }}
        >
          relative improvement
        </p>
      </div>

      {/* Right: status badge */}
      <div className="flex-shrink-0">
        <Badge variant={badgeVariant} />
      </div>
    </div>
  )
}
