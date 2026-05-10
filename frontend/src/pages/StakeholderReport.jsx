import { useParams, Link } from 'react-router-dom'
import { FileText, CheckCircle2, TrendingUp, Share2, AlertTriangle, Zap } from 'lucide-react'
import PageShell from '../components/layout/PageShell'
import Button from '../components/ui/Button'
import { useStreamingReport } from '../hooks/useStreamingReport'
import ReportHeader from '../components/report/ReportHeader'
import RecommendationBadge from '../components/report/RecommendationBadge'
import ReportSection from '../components/report/ReportSection'
import GeneratingProgress from '../components/report/GeneratingProgress'
import ReportActions from '../components/report/ReportActions'

// ---------------------------------------------------------------------------
// Fallback banner — shown when AI was unavailable during generation
// ---------------------------------------------------------------------------
function FallbackBanner() {
  return (
    <div
      className="flex items-start gap-3 px-4 py-3 rounded-lg mb-8 text-sm print:hidden"
      style={{
        backgroundColor: 'rgba(245,158,11,0.08)',
        border: '1px solid rgba(245,158,11,0.3)',
      }}
    >
      <AlertTriangle size={15} style={{ color: 'var(--color-accent-amber)', flexShrink: 0, marginTop: 1 }} />
      <p style={{ color: 'var(--color-text-secondary)' }}>
        <span className="font-semibold" style={{ color: 'var(--color-accent-amber)' }}>
          Template report
        </span>{' '}
        — This report was generated from templates. AI interpretation was unavailable.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Empty state — no report exists yet
// ---------------------------------------------------------------------------
function EmptyState({ onGenerate, generating }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 px-4 text-center">
      <div
        className="w-16 h-16 rounded-2xl flex items-center justify-center mb-6"
        style={{ backgroundColor: 'rgba(59,130,246,0.1)' }}
      >
        <FileText size={28} style={{ color: 'var(--color-accent-blue)' }} />
      </div>

      <h2
        className="font-display font-bold text-xl mb-2"
        style={{ color: 'var(--color-text-primary)' }}
      >
        Generate Stakeholder Report
      </h2>
      <p
        className="text-sm mb-8 max-w-sm leading-relaxed"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        A plain-English summary of your experiment results, written for executives and product teams.
      </p>

      {/* Feature bullets */}
      <div className="flex flex-col gap-3 mb-10 text-left">
        {[
          { Icon: CheckCircle2, text: 'Clear verdict and business impact' },
          { Icon: TrendingUp, text: 'Plain language, no statistical jargon' },
          { Icon: Share2, text: 'Downloadable and shareable' },
        ].map(({ Icon, text }) => (
          <div key={text} className="flex items-center gap-3">
            <Icon size={15} style={{ color: 'var(--color-accent-green)', flexShrink: 0 }} />
            <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              {text}
            </span>
          </div>
        ))}
      </div>

      <Button size="lg" onClick={onGenerate} loading={generating}>
        <Zap size={16} strokeWidth={2.5} />
        Generate Report
      </Button>

      <p
        className="mt-3 text-xs"
        style={{ color: 'var(--color-text-muted)' }}
      >
        ~15 seconds
      </p>
      <p
        className="mt-1 text-xs"
        style={{ color: 'var(--color-text-muted)' }}
      >
        Uses Claude AI · ~$0.04
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Parse markdown into section array if sections not provided by API
// ---------------------------------------------------------------------------
function parseMarkdownSections(markdown) {
  if (!markdown) return []
  const sections = []
  const lines = markdown.split('\n')
  let current = null

  for (const line of lines) {
    const h2 = line.match(/^##\s+(.+)/)
    if (h2) {
      if (current) sections.push(current)
      current = { title: h2[1].trim(), content: '' }
    } else if (current) {
      current.content += line + '\n'
    }
  }
  if (current) sections.push(current)

  // If no ## headers found, return the whole thing as one block
  if (sections.length === 0 && markdown.trim()) {
    sections.push({ title: 'Report', content: markdown })
  }

  return sections
}

// Known section title patterns to assign section numbers
const SECTION_TITLE_MAP = {
  'executive summary': 1,
  'business impact': 2,
  'what we tested': 3,
  results: 4,
  'who it worked for': 5,
  concerns: 6,
  recommendation: 7,
  'technical appendix': 8,
}

function assignSectionNumber(title, index) {
  const lower = title.toLowerCase()
  for (const [key, num] of Object.entries(SECTION_TITLE_MAP)) {
    if (lower.includes(key)) return num
  }
  return index + 1
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function StakeholderReport() {
  const { id } = useParams()

  const {
    report,
    generating,
    progress,
    error,
    generate,
    experimentName,
    isFallback,
    longRunning,
    sectionNames,
  } = useStreamingReport(id)

  // Resolve sections from API response or parse from markdown
  const resolvedSections = (() => {
    if (!report) return []
    if (report.sections?.length > 0) {
      return report.sections.map((s) => ({
        number: s.section_number ?? assignSectionNumber(s.title, 0),
        title: s.title,
        content: s.content,
      }))
    }
    return parseMarkdownSections(report.markdown).map((s, i) => ({
      number: assignSectionNumber(s.title, i),
      title: s.title,
      content: s.content,
    }))
  })()

  const pageTitle = experimentName ?? id
  const breadcrumbs = [
    { label: 'Experiments', href: '/experiments' },
    { label: pageTitle, href: `/experiments/${id}` },
    { label: 'Report' },
  ]

  return (
    <>
      {/* Print stylesheet — hides chrome, shows clean document */}
      <style>{`
        @media print {
          [data-sidebar], nav, .print\\:hidden { display: none !important; }
          body { background: white !important; color: #111 !important; }
          [data-report-content] { max-width: 100% !important; padding: 0 !important; }
        }
      `}</style>

      <PageShell
        breadcrumbs={breadcrumbs}
        actions={
          !generating && !report ? null : (
            <div className="flex items-center gap-2">
              <Link to={`/experiments/${id}`}>
                <Button variant="ghost" size="sm">
                  ← Results
                </Button>
              </Link>
            </div>
          )
        }
      >
        {/* ── GENERATING STATE ─────────────────────────────────────────── */}
        {generating && (
          <GeneratingProgress
            currentSection={progress.currentSection}
            totalSections={progress.totalSections}
            sectionName={progress.sectionName}
            sectionNames={sectionNames}
            longRunning={longRunning}
          />
        )}

        {/* ── EMPTY STATE ──────────────────────────────────────────────── */}
        {!generating && !report && (
          <>
            <EmptyState onGenerate={generate} generating={generating} />
            {error && (
              <div
                className="mt-4 p-4 rounded-lg text-sm text-center"
                style={{
                  backgroundColor: 'rgba(239,68,68,0.08)',
                  color: 'var(--color-accent-red)',
                  border: '1px solid rgba(239,68,68,0.2)',
                }}
              >
                {error.message ?? 'Report generation failed. Please try again.'}
              </div>
            )}
          </>
        )}

        {/* ── REPORT DOCUMENT ──────────────────────────────────────────── */}
        {!generating && report && (
          <div
            className="max-w-[720px] mx-auto px-2 pb-24"
            data-report-content
          >
            {isFallback && <FallbackBanner />}

            <ReportHeader
              experimentName={experimentName ?? 'Experiment'}
              generatedAt={report.generatedAt}
            />

            <RecommendationBadge
              recommendation={report.recommendation}
              confidence={report.confidence}
              reasoning={report.confidenceReasoning}
            />

            {/* Report sections */}
            {resolvedSections.map((section) => (
              <ReportSection
                key={section.number}
                number={section.number}
                title={section.title}
                content={section.content}
                recommendation={report.recommendation}
              />
            ))}

            {/* Fallback: render raw markdown if no sections parsed */}
            {resolvedSections.length === 0 && report.markdown && (
              <div
                className="text-sm leading-relaxed whitespace-pre-wrap"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                {report.markdown}
              </div>
            )}

            {/* Human review notice */}
            <div
              className="mt-12 p-4 rounded-lg text-sm print:hidden"
              style={{
                backgroundColor: 'rgba(245,158,11,0.06)',
                border: '1px solid rgba(245,158,11,0.2)',
              }}
            >
              <span
                className="font-semibold"
                style={{ color: 'var(--color-accent-amber)' }}
              >
                Human review required
              </span>{' '}
              <span style={{ color: 'var(--color-text-secondary)' }}>
                — AI-generated reports must be reviewed before external distribution.
                Verify key figures against the raw statistics.
              </span>
            </div>
          </div>
        )}
      </PageShell>

      {/* Sticky action bar — shown only when report is visible */}
      {!generating && report && (
        <ReportActions
          experimentId={id}
          generatedAt={report.generatedAt}
          markdown={report.markdown}
        />
      )}
    </>
  )
}
