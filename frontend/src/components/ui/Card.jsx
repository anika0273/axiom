import { clsx } from 'clsx'

const ACCENT_COLORS = {
  blue: 'var(--color-accent-blue)',
  green: 'var(--color-accent-green)',
  amber: 'var(--color-accent-amber)',
  red: 'var(--color-accent-red)',
}

/**
 * Card container with surface elevation and optional accent border.
 * @param {Object} props
 * @param {'default'|'elevated'|'accent'} [props.variant='default']
 * @param {'blue'|'green'|'amber'|'red'} [props.accentColor='blue']
 * @param {string} [props.className]
 */
export default function Card({
  variant = 'default',
  accentColor = 'blue',
  children,
  className,
  ...props
}) {
  const isAccent = variant === 'accent'

  return (
    <div
      className={clsx(
        'rounded-md border border-subtle',
        variant === 'default' && 'bg-card shadow-card',
        variant === 'elevated' && 'bg-elevated shadow-elevated',
        isAccent && 'bg-card shadow-card border-l-2',
        className,
      )}
      style={isAccent ? { borderLeftColor: ACCENT_COLORS[accentColor] } : undefined}
      {...props}
    >
      {children}
    </div>
  )
}
