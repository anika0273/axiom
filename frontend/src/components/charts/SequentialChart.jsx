import { memo } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div
      className="rounded-lg border px-3 py-2 text-xs shadow-lg font-mono"
      style={{
        backgroundColor: 'var(--color-bg-elevated)',
        borderColor: 'var(--color-border-subtle)',
        color: 'var(--color-text-primary)',
      }}
    >
      <p style={{ color: 'var(--color-text-muted)' }}>Day {label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} style={{ color: p.stroke ?? p.fill }}>
          {p.name}: {p.value?.toFixed(3)}
        </p>
      ))}
    </div>
  )
}

/**
 * Sequential testing timeline showing z-statistic vs O'Brien-Fleming boundaries.
 * Renders nothing if data is null or empty.
 *
 * @param {Object} props
 * @param {Array<{ day: number, zStat: number, upperBound: number, lowerBound: number }>|null} props.data
 * @param {number|null} props.significanceDay - day significance was reached (draws a vertical green line)
 * @param {boolean} [props.isRunning]
 */
const SequentialChart = memo(function SequentialChart({ data, significanceDay, isRunning = false }) {
  if (!data?.length) return null

  const minZ = Math.min(...data.map((d) => d.lowerBound ?? 0, d.zStat ?? 0))
  const maxZ = Math.max(...data.map((d) => d.upperBound ?? 0, d.zStat ?? 0))
  const domain = [Math.floor(minZ) - 0.5, Math.ceil(maxZ) + 0.5]

  return (
    <div
      className="rounded-lg border border-subtle p-5 mb-6"
      style={{ backgroundColor: 'var(--color-bg-card)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <p
          className="text-xs uppercase tracking-widest font-medium"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Sequential Testing Timeline
        </p>
        {isRunning && (
          <span
            className="text-[10px] font-medium uppercase tracking-widest px-2 py-0.5 rounded-full border flex items-center gap-1.5"
            style={{
              color: 'var(--color-accent-blue)',
              borderColor: 'rgba(59,130,246,0.3)',
              backgroundColor: 'rgba(59,130,246,0.08)',
            }}
          >
            <span
              className="w-1.5 h-1.5 rounded-full animate-pulse"
              style={{ backgroundColor: 'var(--color-accent-blue)' }}
            />
            Experiment in progress
          </span>
        )}
      </div>

      <div style={{ height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--color-border-subtle)"
              vertical={false}
            />
            <XAxis
              dataKey="day"
              tick={{ fontSize: 10, fill: 'var(--color-text-muted)', fontFamily: 'DM Mono' }}
              axisLine={false}
              tickLine={false}
              label={{ value: 'Day', position: 'insideBottomRight', offset: -4, fontSize: 10, fill: 'var(--color-text-muted)' }}
            />
            <YAxis
              domain={domain}
              tick={{ fontSize: 10, fill: 'var(--color-text-muted)', fontFamily: 'DM Mono' }}
              axisLine={false}
              tickLine={false}
              width={36}
              label={{ value: 'z', angle: -90, position: 'insideLeft', offset: 8, fontSize: 10, fill: 'var(--color-text-muted)' }}
            />
            <Tooltip content={<CustomTooltip />} />

            {/* Shaded area between boundaries */}
            <ReferenceArea
              y1={data[0]?.lowerBound}
              y2={data[0]?.upperBound}
              fill="rgba(239,68,68,0.08)"
              stroke="none"
            />

            {/* Significance day marker */}
            {significanceDay != null && (
              <ReferenceLine
                x={significanceDay}
                stroke="var(--color-accent-green)"
                strokeDasharray="5 3"
                strokeWidth={1.5}
                label={{
                  value: `Significance reached — Day ${significanceDay}`,
                  position: 'top',
                  fontSize: 10,
                  fill: 'var(--color-accent-green)',
                  fontFamily: 'DM Mono',
                }}
              />
            )}

            {/* Upper boundary */}
            <Line
              type="monotone"
              dataKey="upperBound"
              name="Upper boundary"
              stroke="var(--color-accent-red)"
              strokeDasharray="5 3"
              strokeWidth={1.5}
              dot={false}
              animationDuration={600}
            />

            {/* Lower boundary */}
            <Line
              type="monotone"
              dataKey="lowerBound"
              name="Lower boundary"
              stroke="var(--color-accent-red)"
              strokeDasharray="5 3"
              strokeWidth={1.5}
              dot={false}
              animationDuration={600}
            />

            {/* Observed z-statistic */}
            <Line
              type="monotone"
              dataKey="zStat"
              name="z-statistic"
              stroke="var(--color-accent-blue)"
              strokeWidth={2}
              dot={false}
              animationDuration={600}
              animationEasing="ease-out"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
})

export default SequentialChart
