import { useState, useEffect, useCallback, useRef } from 'react'

const API_BASE = 'http://localhost:8000'

const SECTION_NAMES = [
  'Executive Summary',
  'Business Impact',
  'What We Tested',
  'Results',
  'Who It Worked For',
  'Concerns',
  'Recommendation',
  'Technical Appendix',
]

/**
 * Manages stakeholder report state: checks for an existing report on mount,
 * exposes generate() to trigger generation, and simulates per-section progress
 * while the backend processes the tool_use call.
 *
 * @param {string|null} experimentId
 * @returns {{
 *   report: object|null,
 *   generating: boolean,
 *   progress: { currentSection: number, totalSections: number, sectionName: string },
 *   error: object|null,
 *   generate: () => void,
 *   experimentName: string|null,
 *   isFallback: boolean,
 * }}
 */
export function useStreamingReport(experimentId) {
  const [report, setReport] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [progress, setProgress] = useState({
    currentSection: 0,
    totalSections: 8,
    sectionName: SECTION_NAMES[0],
  })
  const [error, setError] = useState(null)
  const [experimentName, setExperimentName] = useState(null)
  const [isFallback, setIsFallback] = useState(false)
  const [longRunning, setLongRunning] = useState(false)

  const progressIntervalRef = useRef(null)
  const longRunningTimerRef = useRef(null)
  const abortRef = useRef(null)

  // On mount: fetch experiment and check for existing report
  useEffect(() => {
    if (!experimentId) return

    const controller = new AbortController()
    abortRef.current = controller

    fetch(`${API_BASE}/api/v1/experiments/${experimentId}`, {
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json' },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((json) => {
        if (!json) return
        const exp = json?.data ?? json
        setExperimentName(exp?.name ?? null)

        const existing = exp?.latest_result?.report_markdown
        if (existing) {
          setReport({
            markdown: existing,
            sections: null,
            recommendation: exp?.latest_result?.recommendation ?? null,
            confidence: null,
            generatedAt: exp?.latest_result?.analyzed_at ?? null,
            isFallback: false,
          })
        }
      })
      .catch(() => {})

    return () => controller.abort()
  }, [experimentId])

  const generate = useCallback(async () => {
    if (!experimentId || generating) return

    setGenerating(true)
    setError(null)
    setLongRunning(false)
    setProgress({ currentSection: 0, totalSections: 8, sectionName: SECTION_NAMES[0] })

    // Simulate per-section progress (~1.8s per section) while backend processes
    let sectionIdx = 0
    progressIntervalRef.current = setInterval(() => {
      sectionIdx = Math.min(sectionIdx + 1, 7)
      setProgress({
        currentSection: sectionIdx,
        totalSections: 8,
        sectionName: SECTION_NAMES[sectionIdx],
      })
    }, 1800)

    // After 30s, show "Still working…" message
    longRunningTimerRef.current = setTimeout(() => setLongRunning(true), 30_000)

    try {
      const controller = new AbortController()
      abortRef.current = controller

      const res = await fetch(
        `${API_BASE}/api/v1/intelligence/experiments/${experimentId}/report`,
        {
          method: 'POST',
          signal: controller.signal,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        },
      )

      clearInterval(progressIntervalRef.current)
      clearTimeout(longRunningTimerRef.current)

      if (!res.ok) {
        throw new Error(`Report generation failed (${res.status})`)
      }

      const json = await res.json()
      const data = json?.data ?? json

      setProgress({ currentSection: 8, totalSections: 8, sectionName: '' })

      const newReport = {
        markdown: data?.markdown_content ?? '',
        sections: data?.sections ?? null,
        recommendation: data?.recommendation ?? null,
        confidence: data?.confidence_level ?? null,
        confidenceReasoning: data?.confidence_reasoning ?? null,
        generatedAt: data?.generated_at ?? new Date().toISOString(),
        isFallback: data?.is_fallback ?? false,
        title: data?.title ?? null,
      }

      setReport(newReport)
      setIsFallback(newReport.isFallback)
    } catch (err) {
      clearInterval(progressIntervalRef.current)
      clearTimeout(longRunningTimerRef.current)

      if (err.name !== 'AbortError') {
        setError({ message: err.message, code: 'GENERATION_FAILED' })
      }
    } finally {
      setGenerating(false)
      setLongRunning(false)
    }
  }, [experimentId, generating])

  useEffect(() => {
    return () => {
      clearInterval(progressIntervalRef.current)
      clearTimeout(longRunningTimerRef.current)
      abortRef.current?.abort()
    }
  }, [])

  return {
    report,
    generating,
    progress,
    error,
    generate,
    experimentName,
    isFallback,
    longRunning,
    sectionNames: SECTION_NAMES,
  }
}
