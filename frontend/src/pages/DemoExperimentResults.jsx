import { useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Sparkles } from 'lucide-react'

import PageShell from '../components/layout/PageShell'
import Button from '../components/ui/Button'
import { DEMO_DATA_BY_SLUG, DEMO_ID_BY_SLUG } from '../data/sampleExperiments'

import VerdictBanner from '../components/results/VerdictBanner'
import MetricsRow from '../components/results/MetricsRow'
import AnomalyFlags from '../components/results/AnomalyFlags'
import SegmentTable from '../components/results/SegmentTable'
import NoveltyPanel from '../components/results/NoveltyPanel'
import AIInterpretationPanel from '../components/results/AIInterpretationPanel'
import MetricComparisonChart from '../components/charts/MetricComparisonChart'
import SequentialChart from '../components/charts/SequentialChart'

/**
 * Normalise the confidence interval from the raw stats to display units
 * (percentage points).
 *
 * Proportion experiments store CI in rate space [0, 1] → multiply by 100
 * to get percentage points (e.g. [0.108, 0.137] → [10.8%, 13.7%]).
 *
 * Mean experiments store CI in absolute metric units (e.g. dollars).
 * Divide by the baseline value to get the relative percentage
 * (e.g. [-9.8 / 249.17 * 100, 43.0 / 249.17 * 100] → [-3.9%, 17.3%]).
 */
function normaliseCi(ci, baseline) {
  if (!ci || ci.length < 2) return null
  const [lo, hi] = ci
  if (Math.abs(lo) <= 1 && Math.abs(hi) <= 1) {
    // Proportion / rate space
    return [lo * 100, hi * 100]
  }
  if (baseline && baseline > 0) {
    // Absolute units — convert to relative %
    return [lo / baseline * 100, hi / baseline * 100]
  }
  return null
}

/**
 * Build the display-ready result object from a demo sample entry.
 * This is analogous to buildResult() in ExperimentResults but takes raw
 * JSON-derived sample data directly (no API experiment object needed).
 */
function buildDemoResult(sample) {
  const { stats, ml, controlN, treatmentN, dailyData, metadata } = sample
  if (!stats?.primary) return null

  const primary = stats.primary
  const baseline = metadata.baseline_metric
  const isProportion = metadata.test_type === 'proportion'

  const canTrust = ml?.can_trust_results ?? true
  const overallVerdict = ml?.overall_verdict ?? 'CLEAN'

  const verdict =
    !canTrust || overallVerdict === 'INVALID'
      ? 'INVALID'
      : primary.is_significant
      ? 'SIGNIFICANT'
      : 'NOT_SIGNIFICANT'

  const [ciLow, ciHigh] = normaliseCi(primary.confidence_interval, baseline) ?? [null, null]

  // For proportion experiments show actual rates; mean experiments show null
  // (MetricsRow renders "—" for null values so the card still appears)
  const controlRate = isProportion ? baseline : null
  const treatmentRate = isProportion ? baseline + primary.lift_abs : null

  const ciHalfWidth =
    ciLow != null && ciHigh != null ? (ciHigh - ciLow) / 2 / 100 : null

  const metricName = metadata.name.split(' ').slice(0, 5).join(' ')

  const metrics = [
    {
      name: metricName,
      control: controlRate ?? 0,
      treatment: treatmentRate ?? 0,
      controlError: ciHalfWidth ? ciHalfWidth * 0.5 : null,
      treatmentError: ciHalfWidth,
      lift: primary.lift_pct ?? 0,
      pValue: primary.p_value,
      isSignificant: primary.is_significant,
    },
  ]

  return {
    verdict,
    isSignificant: primary.is_significant,
    pValue: primary.p_value,
    ciLow,
    ciHigh,
    liftPct: primary.lift_pct ?? 0,
    liftAbs: primary.lift_abs ?? 0,
    controlRate,
    treatmentRate,
    controlN,
    treatmentN,
    recommendation: stats.overall_recommendation,
    testType: primary.test_type,
    interpretation: primary.interpretation,
    warnings: stats.warnings ?? [],
    plainEnglish: stats.plain_english,
    overallVerdict,
    canTrust,
    anomaly: ml?.anomaly,
    segments: ml?.segments,
    novelty: ml?.novelty,
    hte: ml?.hte,
    keyInsights: ml?.key_insights ?? [],
    metrics,
    sequential: stats.sequential_status ?? null,
    dailyData: dailyData ?? null,
  }
}

function NotFoundState({ name }) {
  return (
    <div className="text-center py-24">
      <p className="font-mono text-4xl font-medium mb-4" style={{ color: 'var(--color-text-muted)' }}>
        404
      </p>
      <h1 className="font-display text-xl font-bold mb-2" style={{ color: 'var(--color-text-primary)' }}>
        Demo not found
      </h1>
      <p className="text-sm mb-8" style={{ color: 'var(--color-text-secondary)' }}>
        No demo dataset named <span className="font-mono">{name}</span> exists.
        Valid options: ecommerce, saas, marketplace.
      </p>
      <Link to="/demo">
        <Button variant="secondary">
          <ArrowLeft size={14} />
          Back to Demos
        </Button>
      </Link>
    </div>
  )
}

export default function DemoExperimentResults() {
  const { name } = useParams()
  const sample = DEMO_DATA_BY_SLUG[name]
  const experimentId = DEMO_ID_BY_SLUG[name] ?? null

  const result = useMemo(() => (sample ? buildDemoResult(sample) : null), [sample])

  if (!sample) {
    return (
      <PageShell breadcrumbs={[{ label: 'Demos', href: '/demo' }, { label: name }]}>
        <NotFoundState name={name} />
      </PageShell>
    )
  }

  const expName = sample.metadata.name
  const description = sample.metadata.description
  const hasCriticalAnomaly = result?.anomaly?.checks?.some(
    (c) => !c.passed && c.severity === 'critical',
  )

  return (
    <PageShell
      breadcrumbs={[
        { label: 'Demos', href: '/demo' },
        { label: sample.metadata.name.split(' ').slice(0, 4).join(' ') },
      ]}
      actions={
        <div className="flex items-center gap-2">
          <Link to="/demo">
            <Button variant="ghost" size="sm">
              <ArrowLeft size={13} />
              All Demos
            </Button>
          </Link>
        </div>
      }
    >
      {/* Experiment header with DEMO badge */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-1.5">
          <span
            className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full border"
            style={{
              color: 'var(--color-accent-blue)',
              borderColor: 'rgba(59,130,246,0.35)',
              backgroundColor: 'rgba(59,130,246,0.1)',
            }}
          >
            <Sparkles size={9} />
            Demo
          </span>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Pre-computed · No API calls
          </span>
        </div>
        <h1
          className="font-display text-xl font-bold"
          style={{ color: 'var(--color-text-primary)' }}
        >
          {expName}
        </h1>
        {description && (
          <p className="text-xs mt-1 max-w-2xl" style={{ color: 'var(--color-text-muted)' }}>
            {description}
          </p>
        )}
      </div>

      {result && (
        <>
          {/* SECTION 1: Verdict Banner */}
          <VerdictBanner
            verdict={result.verdict}
            pValue={result.pValue}
            ciLow={result.ciLow}
            ciHigh={result.ciHigh}
            liftPct={result.liftPct}
            status="completed"
          />

          {/* SECTION 3 (CRITICAL): Anomaly flags above chart */}
          {hasCriticalAnomaly && <AnomalyFlags anomaly={result.anomaly} />}

          {/* SECTION 2: Key metrics row */}
          <MetricsRow
            controlRate={result.controlRate}
            treatmentRate={result.treatmentRate}
            controlN={result.controlN}
            treatmentN={result.treatmentN}
            liftPct={result.liftPct}
            ciLow={result.ciLow}
            ciHigh={result.ciHigh}
            isSignificant={result.isSignificant}
          />

          {/* SECTION 3 (WARNING): Non-critical anomaly flags below metrics */}
          {!hasCriticalAnomaly && <AnomalyFlags anomaly={result.anomaly} />}

          {/* Key insights */}
          {result.keyInsights?.length > 0 && (
            <div className="mb-6 space-y-2">
              {result.keyInsights.map((insight, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 text-sm px-4 py-3 rounded-lg"
                  style={{
                    backgroundColor: 'var(--color-bg-elevated)',
                    color: 'var(--color-text-secondary)',
                  }}
                >
                  <span
                    className="font-mono text-xs font-bold mt-0.5 flex-shrink-0"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  {insight}
                </div>
              ))}
            </div>
          )}

          {/* SECTION 4: Metric comparison chart */}
          <MetricComparisonChart
            metrics={result.metrics}
            title={`Primary Metric Comparison · ${result.testType ?? 'z-test'}`}
          />

          {/* SECTION 5: Sequential (hidden when null) */}
          <SequentialChart
            data={result.sequential}
            significanceDay={null}
            isRunning={false}
          />

          {/* SECTION 6: Segments */}
          {result.segments && (
            <div id="segments">
              <SegmentTable segments={result.segments} hte={result.hte} />
            </div>
          )}

          {/* SECTION 7: Novelty */}
          <NoveltyPanel novelty={result.novelty} dailyData={result.dailyData} />

          {/* Interesting details banner */}
          {sample.metadata.what_is_interesting && (
            <div
              className="rounded-lg border p-4 mb-6"
              style={{
                borderColor: 'rgba(59,130,246,0.25)',
                backgroundColor: 'rgba(59,130,246,0.05)',
                borderLeftWidth: 3,
                borderLeftColor: 'var(--color-accent-blue)',
              }}
            >
              <p
                className="text-xs uppercase tracking-widest font-medium mb-1"
                style={{ color: 'var(--color-accent-blue)' }}
              >
                What makes this dataset interesting
              </p>
              <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                {sample.metadata.what_is_interesting}
              </p>
            </div>
          )}

          {/* SECTION 8: AI Interpretation */}
          <div id="interpretation">
            <AIInterpretationPanel experimentId={experimentId} experimentName={expName} />
          </div>
        </>
      )}

      <style>{`
        @media print {
          aside, nav { display: none !important; }
          [class*="md:ml-sidebar"] { margin-left: 0 !important; }
          #interpretation { display: none !important; }
        }
      `}</style>
    </PageShell>
  )
}
