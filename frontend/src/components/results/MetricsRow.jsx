function fmtPct(v, decimals = 2) {
  return `${(v * 100).toFixed(decimals)}%`
}

function fmtN(n) {
  return n != null ? `n=${n.toLocaleString()} users` : ''
}

/**
 * Four StatCards in a horizontal row showing key experiment metrics.
 * @param {Object} props
 * @param {number} props.controlRate   - e.g. 0.10
 * @param {number} props.treatmentRate - e.g. 0.2226
 * @param {number|null} props.controlN
 * @param {number|null} props.treatmentN
 * @param {number} props.liftPct       - relative lift %, e.g. 119.4
 * @param {number|null} props.ciLow    - absolute pp, e.g. 10.84
 * @param {number|null} props.ciHigh   - absolute pp, e.g. 13.68
 * @param {boolean} props.isSignificant
 */
export default function MetricsRow({
  controlRate,
  treatmentRate,
  controlN,
  treatmentN,
  liftPct,
  ciLow,
  ciHigh,
  isSignificant,
}) {
  const sigColor = isSignificant ? 'var(--color-accent-green)' : 'var(--color-text-muted)'
  const liftColor =
    liftPct < 0
      ? 'var(--color-accent-red)'
      : isSignificant
      ? 'var(--color-accent-green)'
      : 'var(--color-accent-amber)'

  const liftStr = `${liftPct >= 0 ? '+' : ''}${liftPct.toFixed(1)}%`

  let ciStr = '—'
  if (ciLow != null && ciHigh != null) {
    const fmt = (v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
    ciStr = `[${fmt(ciLow)}, ${fmt(ciHigh)}]`
  }

  const cards = [
    {
      label: 'Control Rate',
      value: fmtPct(controlRate),
      sub: fmtN(controlN),
      accentColor: 'var(--color-text-muted)',
      valueColor: 'var(--color-text-primary)',
    },
    {
      label: 'Treatment Rate',
      value: fmtPct(treatmentRate),
      sub: fmtN(treatmentN),
      accentColor: sigColor,
      valueColor: 'var(--color-text-primary)',
    },
    {
      label: 'Relative Lift',
      value: liftStr,
      sub: isSignificant ? 'Significant' : 'Not significant',
      accentColor: liftColor,
      valueColor: liftColor,
    },
    {
      label: 'Confidence Interval',
      value: ciStr,
      sub: '95% confidence',
      accentColor: sigColor,
      valueColor: 'var(--color-text-primary)',
    },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {cards.map((card) => (
        <div
          key={card.label}
          className="rounded-lg border border-subtle bg-card p-4"
          style={{ borderLeftWidth: 3, borderLeftColor: card.accentColor }}
        >
          <p
            className="text-xs uppercase tracking-widest font-medium mb-2"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {card.label}
          </p>
          <p
            className="font-mono text-2xl font-medium leading-none mb-1.5"
            style={{ color: card.valueColor }}
          >
            {card.value}
          </p>
          {card.sub && (
            <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {card.sub}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}
