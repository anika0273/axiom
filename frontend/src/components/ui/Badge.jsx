import {
  CheckCircle2,
  MinusCircle,
  AlertTriangle,
  XCircle,
  Activity,
  FileText,
} from 'lucide-react'

const CONFIG = {
  significant: {
    icon: CheckCircle2,
    label: 'Significant',
    bg: 'rgba(16,185,129,0.1)',
    border: 'rgba(16,185,129,0.25)',
    color: 'var(--color-accent-green)',
  },
  'not-significant': {
    icon: MinusCircle,
    label: 'Not Significant',
    bg: 'rgba(71,85,105,0.15)',
    border: 'rgba(71,85,105,0.3)',
    color: 'var(--color-text-secondary)',
  },
  warning: {
    icon: AlertTriangle,
    label: 'Warning',
    bg: 'rgba(245,158,11,0.1)',
    border: 'rgba(245,158,11,0.25)',
    color: 'var(--color-accent-amber)',
  },
  invalid: {
    icon: XCircle,
    label: 'Invalid',
    bg: 'rgba(239,68,68,0.1)',
    border: 'rgba(239,68,68,0.25)',
    color: 'var(--color-accent-red)',
  },
  running: {
    icon: Activity,
    label: 'Running',
    bg: 'rgba(59,130,246,0.1)',
    border: 'rgba(59,130,246,0.25)',
    color: 'var(--color-accent-blue)',
  },
  completed: {
    icon: CheckCircle2,
    label: 'Completed',
    bg: 'rgba(71,85,105,0.15)',
    border: 'rgba(71,85,105,0.3)',
    color: 'var(--color-text-secondary)',
  },
  draft: {
    icon: FileText,
    label: 'Draft',
    bg: 'rgba(30,45,64,0.6)',
    border: 'var(--color-border-subtle)',
    color: 'var(--color-text-muted)',
  },
}

/**
 * Status badge pill with icon and label.
 * @param {Object} props
 * @param {'significant'|'not-significant'|'warning'|'invalid'|'running'|'completed'|'draft'} props.variant
 * @param {string} [props.label] - Override the default label
 */
export default function Badge({ variant, label, className = '' }) {
  const config = CONFIG[variant] ?? CONFIG.draft
  const Icon = config.icon

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-medium uppercase tracking-widest ${className}`}
      style={{
        backgroundColor: config.bg,
        borderColor: config.border,
        color: config.color,
      }}
    >
      <Icon size={10} strokeWidth={2.5} />
      {label ?? config.label}
    </span>
  )
}
