import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { TrendingDown, Minus, BookOpen, AlertCircle } from 'lucide-react'

const PATTERN_CONFIG = {
  NOVELTY: {
    label: 'NOVELTY DECAY',
    color: 'var(--color-accent-amber)',
    bg: 'rgba(245,158,11,0.08)',
    border: 'rgba(245,158,11,0.3)',
    Icon: TrendingDown,
    bannerText:
      'Declining effect detected — current lift may not persist at steady state.',
  },
  STABLE: {
    label: 'STABLE',
    color: 'var(--color-accent-green)',
    bg: 'rgba(16,185,129,0.06)',
    border: 'rgba(16,185,129,0.2)',
    Icon: Minus,
    bannerText: null,
  },
  LEARNING: {
    label: 'LEARNING CURVE',
    color: 'var(--color-accent-blue)',
    bg: 'rgba(59,130,246,0.06)',
    border: 'rgba(59,130,246,0.2)',
    Icon: BookOpen,
    bannerText: 'Effect is still growing — users may still be adapting to the change.',
  },
  INSUFFICIENT: {
    label: 'INSUFFICIENT DATA',
    color: 'var(--color-text-muted)',
    bg: 'transparent',
    border: 'var(--color-border-subtle)',
    Icon: AlertCircle,
    bannerText: 'Not enough data to classify novelty pattern.',
  },
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div
      className="rounded-lg border px-3 py-2 text-xs font-mono shadow-lg"
      style={{
        backgroundColor: 'var(--color-bg-elevated)',
        borderColor: 'var(--color-border-subtle)',
        color: 'var(--color-text-primary)',
      }}
    >
      <p style={{ color: 'var(--color-text-muted)' }}>Day {label}</p>
      <p style={{ color: 'var(--color-accent-blue)' }}>
        Effect: {payload[0]?.value != null ? `+${(payload[0].value * 100).toFixed(1)}%` : '—'}
      </p>
    </div>
  )
}

/**
 * Novelty detection panel with a mini line chart of daily treatment effect.
 * Hidden when novelty data is null.
 *
 * @param {Object} props
 * @param {{ pattern: string, recommendation: string, projected_stable_lift: number, initial_lift: number }|null} props.novelty
 * @param {Array|null} props.dailyData - array of { day, effect } for the mini chart
 */
export default function NoveltyPanel({ novelty, dailyData }) {
  if (!novelty) return null

  const cfg = PATTERN_CONFIG[novelty.pattern] ?? PATTERN_CONFIG.INSUFFICIENT
  const Icon = cfg.Icon
  const chartData = dailyData?.map((d) => ({ day: d.day, effect: d.effect })) ?? []
  const stableLiftStr =
    novelty.projected_stable_lift != null && novelty.projected_stable_lift !== 0
      ? `+${(novelty.projected_stable_lift * 100).toFixed(1)}%`
      : '~0%'

  return (
    <div className="mb-6" id="novelty">
      {/* Section header */}
      <div className="flex items-center gap-3 mb-4">
        <h2
          className="font-display font-bold text-base"
          style={{ color: 'var(--color-text-primary)' }}
        >
          Novelty Detection
        </h2>
        <span
          className="text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full"
          style={{
            color: cfg.color,
            backgroundColor: cfg.bg,
            border: `1px solid ${cfg.border}`,
          }}
        >
          {cfg.label}
        </span>
      </div>

      {/* Alert banner for NOVELTY */}
      {cfg.bannerText && (
        <div
          className="rounded-lg border p-3 mb-4 flex items-start gap-2"
          style={{
            background: cfg.bg,
            borderColor: cfg.border,
            borderLeftWidth: 3,
            borderLeftColor: cfg.color,
          }}
        >
          <Icon size={15} style={{ color: cfg.color, flexShrink: 0, marginTop: 1 }} />
          <div>
            <p className="text-sm" style={{ color: 'var(--color-text-primary)' }}>
              {cfg.bannerText}
            </p>
            {novelty.pattern === 'NOVELTY' && (
              <p className="text-xs mt-1" style={{ color: 'var(--color-text-secondary)' }}>
                Estimated steady-state effect:{' '}
                <span className="font-mono" style={{ color: cfg.color }}>
                  {stableLiftStr}
                </span>
              </p>
            )}
          </div>
        </div>
      )}

      {/* Mini chart */}
      {chartData.length > 0 && (
        <div
          className="rounded-lg border border-subtle p-4"
          style={{ backgroundColor: 'var(--color-bg-card)', height: 200 }}
        >
          <p
            className="text-xs uppercase tracking-widest font-medium mb-3"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Daily Treatment Effect
          </p>
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <XAxis
                dataKey="day"
                tick={{ fontSize: 10, fill: 'var(--color-text-muted)', fontFamily: 'DM Mono' }}
                tickLine={false}
                axisLine={false}
                label={{ value: 'Day', position: 'insideBottomRight', offset: -4, fontSize: 10, fill: 'var(--color-text-muted)' }}
              />
              <YAxis
                tick={{ fontSize: 10, fill: 'var(--color-text-muted)', fontFamily: 'DM Mono' }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                width={40}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="effect"
                stroke="var(--color-accent-blue)"
                strokeWidth={2}
                dot={false}
                animationDuration={600}
                animationEasing="ease-out"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Recommendation text */}
      {novelty.recommendation && (
        <p className="text-xs mt-3" style={{ color: 'var(--color-text-secondary)' }}>
          {novelty.recommendation}
        </p>
      )}
    </div>
  )
}
