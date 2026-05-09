import { TrendingUp, TrendingDown } from 'lucide-react'
import { AreaChart, Area, ResponsiveContainer } from 'recharts'
import { clsx } from 'clsx'

/**
 * Metric card displaying a large number with optional trend and sparkline.
 * @param {Object} props
 * @param {string} props.label - Metric label
 * @param {string|number} props.value - Primary display value (rendered in DM Mono)
 * @param {number} [props.trend] - Trend percentage (+/-). Omit to hide trend indicator.
 * @param {Array<{value: number}>} [props.sparkline] - Data for mini area chart
 * @param {string} [props.className]
 */
export default function StatCard({ label, value, trend, sparkline, className }) {
  const hasTrend = trend !== undefined && trend !== null
  const isPositive = trend > 0

  return (
    <div
      className={clsx(
        'bg-card border border-subtle rounded-lg p-4 flex flex-col gap-3',
        className,
      )}
    >
      <p className="text-xs text-secondary uppercase tracking-widest font-medium">{label}</p>

      <div className="flex items-end justify-between gap-2">
        <span className="font-mono text-2xl font-medium text-primary leading-none">
          {value}
        </span>

        {hasTrend && (
          <span
            className={clsx(
              'inline-flex items-center gap-1 text-xs font-medium font-mono',
              isPositive ? 'text-green' : 'text-red',
            )}
          >
            {isPositive ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
            {isPositive ? '+' : ''}{trend}%
          </span>
        )}
      </div>

      {sparkline && sparkline.length > 0 && (
        <div className="h-10 -mx-1">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={sparkline} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--color-accent-blue)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--color-accent-blue)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="value"
                stroke="var(--color-accent-blue)"
                strokeWidth={1.5}
                fill="url(#sparkGrad)"
                dot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
