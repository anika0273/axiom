import { AlertTriangle, XCircle, Info, ShieldAlert } from 'lucide-react'

const SEVERITY_CONFIG = {
  critical: {
    Icon: XCircle,
    color: 'var(--color-accent-red)',
    bg: 'rgba(239,68,68,0.06)',
    border: 'rgba(239,68,68,0.3)',
    label: 'CRITICAL',
    labelBg: 'rgba(239,68,68,0.15)',
  },
  warning: {
    Icon: AlertTriangle,
    color: 'var(--color-accent-amber)',
    bg: 'rgba(245,158,11,0.06)',
    border: 'rgba(245,158,11,0.3)',
    label: 'WARNING',
    labelBg: 'rgba(245,158,11,0.15)',
  },
  info: {
    Icon: Info,
    color: 'var(--color-text-muted)',
    bg: 'transparent',
    border: 'var(--color-border-subtle)',
    label: 'INFO',
    labelBg: 'rgba(71,85,105,0.2)',
  },
}

/**
 * Renders anomaly warning banners for any failed anomaly checks.
 * Returns null when there are no failed checks.
 *
 * @param {Object} props
 * @param {{ checks: Array }} props.anomaly
 */
export default function AnomalyFlags({ anomaly }) {
  if (!anomaly?.checks) return null

  const failed = anomaly.checks.filter((c) => !c.passed)
  if (failed.length === 0) return null

  return (
    <div className="space-y-3 mb-6">
      {failed.map((check) => {
        const cfg = SEVERITY_CONFIG[check.severity] ?? SEVERITY_CONFIG.warning
        const Icon = cfg.Icon

        return (
          <div
            key={check.name}
            className="rounded-lg border p-4 flex gap-3"
            style={{
              background: cfg.bg,
              borderColor: cfg.border,
              borderLeftWidth: 3,
              borderLeftColor: cfg.color,
            }}
          >
            <ShieldAlert
              size={18}
              style={{ color: cfg.color, flexShrink: 0, marginTop: 1 }}
              strokeWidth={2}
            />

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span
                  className="text-[10px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded"
                  style={{ color: cfg.color, backgroundColor: cfg.labelBg }}
                >
                  {cfg.label}
                </span>
                <span
                  className="font-mono text-xs font-medium"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {check.name.replace(/_/g, ' ')}
                </span>
              </div>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--color-text-primary)' }}>
                {check.description}
              </p>
              {check.action && check.action !== 'No action required.' && (
                <p
                  className="text-xs mt-1.5 flex items-center gap-1"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  <Icon size={12} />
                  {check.action}
                </p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
