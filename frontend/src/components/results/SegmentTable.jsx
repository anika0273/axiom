import { Star, TrendingUp, TrendingDown, Minus } from 'lucide-react'

function liftStyle(lift, significant) {
  if (!significant) return { color: 'var(--color-text-muted)' }
  return { color: lift >= 0 ? 'var(--color-accent-green)' : 'var(--color-accent-red)' }
}

function rowBorder(lift, significant) {
  if (!significant) return {}
  if (lift >= 0) return { borderLeftWidth: 3, borderLeftColor: 'var(--color-accent-green)' }
  return { borderLeftWidth: 3, borderLeftColor: 'var(--color-accent-red)' }
}

function fmtLift(lift) {
  const pct = (lift * 100).toFixed(1)
  return `${lift >= 0 ? '+' : ''}${pct}%`
}

/**
 * Segment analysis table + HTE subsection.
 * @param {Object} props
 * @param {{ segments: Array, responsive_segments: number[], overall_recommendation: string }} props.segments
 * @param {{ ate: number, stability_score: number, business_recommendation: string, top_interactions: string[] }|null} props.hte
 */
export default function SegmentTable({ segments, hte }) {
  if (!segments?.segments?.length) return null

  const { segments: segs, responsive_segments, overall_recommendation, optimal_k } = segments
  const topModifier = hte?.top_interactions?.[0]?.replace(/_x_treat$/, '').replace(/_/g, ' ')

  return (
    <div className="mb-6">
      {/* Section header */}
      <div className="flex items-center gap-3 mb-4">
        <h2 className="font-display font-bold text-base" style={{ color: 'var(--color-text-primary)' }}>
          Segment Analysis
        </h2>
        <span
          className="text-[11px] font-medium px-2 py-0.5 rounded-full border uppercase tracking-widest"
          style={{
            color: 'var(--color-accent-blue)',
            borderColor: 'rgba(59,130,246,0.3)',
            backgroundColor: 'rgba(59,130,246,0.08)',
          }}
        >
          {optimal_k} segments discovered
        </span>
      </div>

      {/* Table */}
      <div
        className="rounded-lg border border-subtle overflow-hidden mb-4"
        style={{ backgroundColor: 'var(--color-bg-card)' }}
      >
        {/* Header */}
        <div
          className="grid gap-4 px-4 py-2.5 border-b border-subtle text-[11px] uppercase tracking-widest font-medium"
          style={{
            gridTemplateColumns: '80px 1fr 80px 110px 90px',
            color: 'var(--color-text-muted)',
            backgroundColor: 'var(--color-bg-elevated)',
          }}
        >
          <span>Segment</span>
          <span>Description</span>
          <span>Size</span>
          <span>Treatment Effect</span>
          <span>Significant?</span>
        </div>

        {/* Rows */}
        {segs.map((seg) => {
          const isResponsive = responsive_segments?.includes(seg.id)
          const style = liftStyle(seg.lift, seg.significant)

          return (
            <div
              key={seg.id}
              className="grid gap-4 px-4 py-3 border-b border-subtle last:border-b-0 text-sm"
              style={{
                gridTemplateColumns: '80px 1fr 80px 110px 90px',
                ...rowBorder(seg.lift, seg.significant),
              }}
            >
              {/* Segment ID */}
              <div className="flex items-center gap-1.5">
                <span className="font-mono font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  Seg {seg.id}
                </span>
                {isResponsive && (
                  <Star size={11} fill="var(--color-accent-amber)" style={{ color: 'var(--color-accent-amber)', flexShrink: 0 }} />
                )}
              </div>

              {/* Description */}
              <span
                className="text-xs leading-relaxed"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                {seg.description}
              </span>

              {/* Size */}
              <span className="font-mono text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                {(seg.size_pct * 100).toFixed(0)}%
              </span>

              {/* Lift */}
              <span className="font-mono font-medium" style={style}>
                {fmtLift(seg.lift)}
              </span>

              {/* Significant */}
              <div className="flex items-center gap-1">
                {seg.significant ? (
                  <>
                    <TrendingUp size={13} style={{ color: seg.lift >= 0 ? 'var(--color-accent-green)' : 'var(--color-accent-red)' }} />
                    <span className="text-xs" style={{ color: seg.lift >= 0 ? 'var(--color-accent-green)' : 'var(--color-accent-red)' }}>
                      Yes
                    </span>
                  </>
                ) : (
                  <>
                    <Minus size={13} style={{ color: 'var(--color-text-muted)' }} />
                    <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      No
                    </span>
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Overall recommendation */}
      {overall_recommendation && (
        <p className="text-xs mb-5" style={{ color: 'var(--color-text-secondary)' }}>
          <Star size={11} className="inline mr-1" style={{ color: 'var(--color-accent-amber)' }} />
          Responsive segments
          &nbsp;·&nbsp;
          {overall_recommendation}
        </p>
      )}

      {/* HTE subsection */}
      {hte && (
        <div
          className="rounded-lg border border-subtle p-4"
          style={{
            backgroundColor: 'var(--color-bg-elevated)',
            borderLeftWidth: 3,
            borderLeftColor: 'var(--color-accent-blue)',
          }}
        >
          <p
            className="text-xs uppercase tracking-widest font-medium mb-2"
            style={{ color: 'var(--color-text-muted)' }}
          >
            HTE Analysis
          </p>
          {topModifier && (
            <p className="text-sm mb-2" style={{ color: 'var(--color-text-primary)' }}>
              Treatment effect was strongest for users with high{' '}
              <span className="font-mono" style={{ color: 'var(--color-text-data)' }}>
                {topModifier}
              </span>
            </p>
          )}
          {hte.business_recommendation && (
            <p className="text-xs mb-3" style={{ color: 'var(--color-text-secondary)' }}>
              {hte.business_recommendation}
            </p>
          )}
          {/* Stability score */}
          <div className="flex items-center gap-3">
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              Model stability
            </span>
            <div
              className="flex-1 rounded-full overflow-hidden"
              style={{ height: 4, backgroundColor: 'var(--color-bg-hover)' }}
            >
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(hte.stability_score * 100).toFixed(0)}%`,
                  backgroundColor:
                    hte.stability_score > 0.8
                      ? 'var(--color-accent-green)'
                      : 'var(--color-accent-amber)',
                  transition: 'width 600ms ease-out',
                }}
              />
            </div>
            <span className="font-mono text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              {(hte.stability_score * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
