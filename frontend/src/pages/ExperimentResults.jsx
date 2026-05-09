import { useEffect, useMemo } from 'react'
import { useParams, Link, useLocation } from 'react-router-dom'
import { RefreshCw, FileText, ArrowLeft } from 'lucide-react'

import PageShell from '../components/layout/PageShell'
import Skeleton from '../components/ui/Skeleton'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { useAPI } from '../hooks/useAPI'
import { SAMPLE_DATA } from '../data/sampleExperiments'

import VerdictBanner from '../components/results/VerdictBanner'
import MetricsRow from '../components/results/MetricsRow'
import AnomalyFlags from '../components/results/AnomalyFlags'
import SegmentTable from '../components/results/SegmentTable'
import NoveltyPanel from '../components/results/NoveltyPanel'
import AIInterpretationPanel from '../components/results/AIInterpretationPanel'
import MetricComparisonChart from '../components/charts/MetricComparisonChart'
import SequentialChart from '../components/charts/SequentialChart'

const API_BASE = 'http://localhost:8000'

function buildResult(experiment, sample) {
  if (!sample) return null

  const { stats, ml, controlN, treatmentN, dailyData } = sample
  if (!stats?.primary) return null

  const primary = stats.primary
  const canTrust = ml?.can_trust_results ?? true
  const overallVerdict = ml?.overall_verdict ?? 'CLEAN'

  const verdict =
    !canTrust || overallVerdict === 'INVALID'
      ? 'INVALID'
      : primary.is_significant
      ? 'SIGNIFICANT'
      : 'NOT_SIGNIFICANT'

  const ciLow = primary.confidence_interval
    ? primary.confidence_interval[0] * 100
    : null
  const ciHigh = primary.confidence_interval
    ? primary.confidence_interval[1] * 100
    : null

  const controlRate = experiment?.baseline_metric ?? 0
  const treatmentRate = controlRate + (primary.lift_abs ?? 0)

  // Half CI-width as error bar on treatment bar
  const ciHalfWidth = ciLow != null && ciHigh != null ? (ciHigh - ciLow) / 2 / 100 : null

  const metrics = [
    {
      name: experiment?.name?.split(' ').slice(0, 4).join(' ') ?? 'Primary Metric',
      control: controlRate,
      treatment: treatmentRate,
      controlError: ciHalfWidth ? ciHalfWidth * 0.5 : null,
      treatmentError: ciHalfWidth,
      lift: primary.lift_pct ?? 0,
      pValue: primary.p_value,
      isSignificant: primary.is_significant,
    },
  ]

  // Sequential data: null for this dataset (no sequential testing)
  const sequential = stats.sequential_status

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
    // ML
    overallVerdict,
    canTrust,
    anomaly: ml?.anomaly,
    segments: ml?.segments,
    novelty: ml?.novelty,
    hte: ml?.hte,
    keyInsights: ml?.key_insights ?? [],
    // Chart inputs
    metrics,
    sequential,
    dailyData: dailyData ?? null,
  }
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton variant="card" className="h-32" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} variant="card" className="h-24" />
        ))}
      </div>
      <Skeleton variant="chart" className="h-80" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Skeleton variant="chart" className="h-48" />
        <Skeleton variant="chart" className="h-48" />
      </div>
    </div>
  )
}

function NotFoundState({ id }) {
  return (
    <div className="text-center py-24">
      <p className="font-mono text-4xl font-medium mb-4" style={{ color: 'var(--color-text-muted)' }}>
        404
      </p>
      <h1 className="font-display text-xl font-bold mb-2" style={{ color: 'var(--color-text-primary)' }}>
        Experiment not found
      </h1>
      <p className="text-sm mb-8" style={{ color: 'var(--color-text-secondary)' }}>
        No experiment with ID <span className="font-mono">{id}</span> exists.
      </p>
      <Link to="/experiments">
        <Button variant="secondary">
          <ArrowLeft size={14} />
          Back to Experiments
        </Button>
      </Link>
    </div>
  )
}

function ErrorState({ message, onRetry }) {
  return (
    <Card variant="accent" accentColor="red" className="p-6 max-w-lg mx-auto mt-12">
      <p className="font-display font-bold mb-2" style={{ color: 'var(--color-text-primary)' }}>
        Failed to load experiment
      </p>
      <p className="text-sm mb-4" style={{ color: 'var(--color-text-secondary)' }}>
        {message ?? 'An unexpected error occurred.'}
      </p>
      <Button variant="secondary" size="sm" onClick={onRetry}>
        <RefreshCw size={13} />
        Retry
      </Button>
    </Card>
  )
}

export default function ExperimentResults() {
  const { id } = useParams()
  const { hash } = useLocation()
  const { data: experiment, loading, error, refetch } = useAPI(
    id ? `${API_BASE}/api/v1/experiments/${id}` : null,
  )

  // Scroll to anchor when hash is present
  useEffect(() => {
    if (hash && !loading) {
      const el = document.querySelector(hash)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [hash, loading])

  const sample = SAMPLE_DATA[id] ?? null
  const result = useMemo(
    () => buildResult(experiment, sample),
    [experiment, sample],
  )

  // --- Loading ---
  if (loading) {
    return (
      <PageShell breadcrumbs={[{ label: 'Experiments', href: '/experiments' }, { label: '…' }]}>
        <LoadingSkeleton />
      </PageShell>
    )
  }

  // --- API error ---
  if (error && error.status === 404) {
    return (
      <PageShell breadcrumbs={[{ label: 'Experiments', href: '/experiments' }, { label: id }]}>
        <NotFoundState id={id} />
      </PageShell>
    )
  }

  if (error) {
    return (
      <PageShell breadcrumbs={[{ label: 'Experiments', href: '/experiments' }, { label: id }]}>
        <ErrorState message={error.message} onRetry={refetch} />
      </PageShell>
    )
  }

  const expName = experiment?.name ?? id
  const expStatus = experiment?.status ?? 'completed'
  const hasCriticalAnomaly = result?.anomaly?.checks?.some(
    (c) => !c.passed && c.severity === 'critical',
  )

  return (
    <PageShell
      breadcrumbs={[
        { label: 'Experiments', href: '/experiments' },
        { label: expName },
      ]}
      actions={
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={refetch}>
            <RefreshCw size={13} />
            Recompute
          </Button>
          <Link to={`/experiments/${id}/report`}>
            <Button size="sm">
              <FileText size={13} />
              Report
            </Button>
          </Link>
        </div>
      }
    >
      {/* No results yet — sample data not available */}
      {!result && (
        <div className="space-y-6">
          <div className="mb-4">
            <h1
              className="font-display text-2xl font-bold mb-2"
              style={{ color: 'var(--color-text-primary)' }}
            >
              {expName}
            </h1>
            {experiment?.description && (
              <p className="text-sm max-w-2xl" style={{ color: 'var(--color-text-secondary)' }}>
                {experiment.description}
              </p>
            )}
          </div>
          <Card className="p-8 text-center">
            <p
              className="font-display text-lg font-bold mb-2"
              style={{ color: 'var(--color-text-primary)' }}
            >
              No analysis available yet
            </p>
            <p className="text-sm mb-4" style={{ color: 'var(--color-text-secondary)' }}>
              This experiment has not been analysed. Run the stats and ML pipeline to see results here.
            </p>
            <Button variant="secondary" size="sm">
              Run Analysis
            </Button>
          </Card>
          <AIInterpretationPanel experimentId={id} experimentName={expName} />
        </div>
      )}

      {/* Full results view */}
      {result && (
        <>
          {/* Experiment name above banner */}
          <div className="mb-4">
            <h1
              className="font-display text-xl font-bold"
              style={{ color: 'var(--color-text-primary)' }}
            >
              {expName}
            </h1>
            {experiment?.description && (
              <p
                className="text-xs mt-1 max-w-2xl"
                style={{ color: 'var(--color-text-muted)' }}
              >
                {experiment.description}
              </p>
            )}
          </div>

          {/* SECTION 1: Verdict Banner */}
          <VerdictBanner
            verdict={result.verdict}
            pValue={result.pValue}
            ciLow={result.ciLow}
            ciHigh={result.ciHigh}
            liftPct={result.liftPct}
            status={expStatus}
          />

          {/* SECTION 3 (CRITICAL): Anomaly flags above chart */}
          {hasCriticalAnomaly && (
            <AnomalyFlags anomaly={result.anomaly} />
          )}

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

          {/* SECTION 3 (WARNING): Non-critical anomaly flags */}
          {!hasCriticalAnomaly && (
            <AnomalyFlags anomaly={result.anomaly} />
          )}

          {/* Key insights (from ML) */}
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

          {/* SECTION 5: Sequential testing timeline (conditional) */}
          <SequentialChart
            data={result.sequential}
            significanceDay={null}
            isRunning={expStatus === 'running'}
          />

          {/* SECTION 6: Segment analysis (conditional) */}
          {result.segments && (
            <div id="segments">
              <SegmentTable segments={result.segments} hte={result.hte} />
            </div>
          )}

          {/* SECTION 7: Novelty detection (conditional) */}
          <NoveltyPanel novelty={result.novelty} dailyData={result.dailyData} />

          {/* SECTION 8: AI interpretation */}
          <div id="interpretation">
            <AIInterpretationPanel experimentId={id} experimentName={expName} />
          </div>
        </>
      )}

      {/* Print styles — inlined here to avoid modifying shared components */}
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
