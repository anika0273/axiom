import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ErrorBar,
  ResponsiveContainer,
  Cell,
} from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div
      className="rounded-lg border px-3 py-2.5 text-xs shadow-lg"
      style={{
        backgroundColor: 'var(--color-bg-elevated)',
        borderColor: 'var(--color-border-subtle)',
      }}
    >
      <p
        className="font-medium mb-1.5"
        style={{ color: 'var(--color-text-primary)' }}
      >
        {label}
      </p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <span
            className="inline-block w-2 h-2 rounded-full"
            style={{ backgroundColor: p.fill }}
          />
          <span style={{ color: 'var(--color-text-secondary)' }}>{p.name}:</span>
          <span className="font-mono font-medium" style={{ color: 'var(--color-text-primary)' }}>
            {(p.value * 100).toFixed(2)}%
          </span>
        </div>
      ))}
    </div>
  )
}

/**
 * Grouped bar chart comparing control vs treatment for each metric.
 * Includes error bars showing ±95% CI half-width on the treatment bar.
 *
 * @param {Object} props
 * @param {Array<{
 *   name: string,
 *   control: number,
 *   treatment: number,
 *   controlError?: number,
 *   treatmentError?: number,
 *   isSignificant?: boolean,
 * }>} props.metrics
 * @param {string} [props.title]
 */
export default function MetricComparisonChart({ metrics, title = 'Primary Metric Comparison' }) {
  if (!metrics?.length) return null

  const treatmentColor = (sig) =>
    sig ? 'var(--color-accent-green)' : 'var(--color-accent-blue)'

  return (
    <div
      className="rounded-lg border border-subtle p-5 mb-6"
      style={{ backgroundColor: 'var(--color-bg-card)' }}
    >
      <p
        className="text-xs uppercase tracking-widest font-medium mb-4"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {title}
      </p>

      <div style={{ height: 320 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={metrics}
            margin={{ top: 8, right: 16, left: 0, bottom: 0 }}
            barCategoryGap="30%"
            barGap={4}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--color-border-subtle)"
              vertical={false}
            />
            <XAxis
              dataKey="name"
              tick={{
                fontSize: 11,
                fill: 'var(--color-text-secondary)',
                fontFamily: 'DM Mono',
              }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
              tick={{
                fontSize: 10,
                fill: 'var(--color-text-muted)',
                fontFamily: 'DM Mono',
              }}
              axisLine={false}
              tickLine={false}
              width={44}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
            <Legend
              wrapperStyle={{
                fontSize: 11,
                color: 'var(--color-text-secondary)',
                paddingTop: 12,
              }}
            />

            {/* Control bars */}
            <Bar
              dataKey="control"
              name="Control"
              fill="var(--color-bg-elevated)"
              stroke="rgba(71,85,105,0.5)"
              strokeWidth={1}
              radius={[3, 3, 0, 0]}
              animationDuration={600}
              animationEasing="ease-out"
            >
              {metrics.map((m) => (
                <Cell key={m.name} fill="rgba(71,85,105,0.35)" stroke="rgba(71,85,105,0.6)" strokeWidth={1} />
              ))}
              <ErrorBar
                dataKey="controlError"
                width={6}
                strokeWidth={1.5}
                stroke="rgba(71,85,105,0.8)"
              />
            </Bar>

            {/* Treatment bars */}
            <Bar
              dataKey="treatment"
              name="Treatment"
              radius={[3, 3, 0, 0]}
              animationDuration={600}
              animationEasing="ease-out"
              animationBegin={100}
            >
              {metrics.map((m) => (
                <Cell
                  key={m.name}
                  fill={treatmentColor(m.isSignificant)}
                  fillOpacity={0.85}
                />
              ))}
              <ErrorBar
                dataKey="treatmentError"
                width={6}
                strokeWidth={1.5}
                stroke="rgba(255,255,255,0.6)"
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Data table */}
      <div
        className="mt-5 rounded-lg border border-subtle overflow-hidden"
        style={{ backgroundColor: 'var(--color-bg-elevated)' }}
      >
        <div
          className="grid text-[10px] uppercase tracking-widest font-medium px-4 py-2 border-b border-subtle"
          style={{
            gridTemplateColumns: '1fr 90px 90px 80px 90px 100px',
            color: 'var(--color-text-muted)',
          }}
        >
          <span>Metric</span>
          <span>Control</span>
          <span>Treatment</span>
          <span>Lift</span>
          <span>p-value</span>
          <span>Significant?</span>
        </div>
        {metrics.map((m) => (
          <div
            key={m.name}
            className="grid px-4 py-2.5 text-xs font-mono border-b border-subtle last:border-b-0"
            style={{
              gridTemplateColumns: '1fr 90px 90px 80px 90px 100px',
              color: 'var(--color-text-secondary)',
            }}
          >
            <span style={{ fontFamily: 'DM Sans', color: 'var(--color-text-primary)' }}>
              {m.name}
            </span>
            <span>{(m.control * 100).toFixed(2)}%</span>
            <span>{(m.treatment * 100).toFixed(2)}%</span>
            <span
              style={{
                color:
                  m.lift > 0
                    ? m.isSignificant
                      ? 'var(--color-accent-green)'
                      : 'var(--color-accent-amber)'
                    : 'var(--color-accent-red)',
              }}
            >
              {m.lift >= 0 ? '+' : ''}{m.lift.toFixed(1)}%
            </span>
            <span>{m.pValue != null ? (m.pValue === 0 ? '<0.001' : m.pValue.toFixed(3)) : '—'}</span>
            <span
              style={{
                color: m.isSignificant
                  ? 'var(--color-accent-green)'
                  : 'var(--color-text-muted)',
              }}
            >
              {m.isSignificant ? '✓ Yes' : '✗ No'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
