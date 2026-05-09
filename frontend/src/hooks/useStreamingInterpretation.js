import { useState, useCallback, useRef } from 'react'

const API_BASE = 'http://localhost:8000'

/**
 * Opens an SSE connection to the interpret endpoint and accumulates streamed text.
 * @param {string|null} experimentId
 * @returns {{ text: string, streaming: boolean, error: object|null, startStream: () => void, stop: () => void }}
 */
export function useStreamingInterpretation(experimentId) {
  const [text, setText] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState(null)
  const esRef = useRef(null)

  const stop = useCallback(() => {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
    setStreaming(false)
  }, [])

  const startStream = useCallback(() => {
    if (!experimentId) return
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }

    setText('')
    setStreaming(true)
    setError(null)

    const url = `${API_BASE}/api/v1/intelligence/experiments/${experimentId}/interpret`
    let es

    try {
      es = new EventSource(url)
    } catch {
      setError({ code: 'STREAM_ERROR', message: 'Failed to open AI connection' })
      setStreaming(false)
      return
    }

    esRef.current = es

    es.onmessage = (event) => {
      if (!event.data || event.data === '[DONE]') {
        setStreaming(false)
        es.close()
        esRef.current = null
        return
      }
      try {
        const parsed = JSON.parse(event.data)
        const chunk = parsed?.text ?? parsed?.delta ?? parsed?.content ?? ''
        if (chunk) setText((prev) => prev + chunk)
      } catch {
        // Non-JSON chunk — treat as raw text
        setText((prev) => prev + event.data)
      }
    }

    es.addEventListener('done', () => {
      setStreaming(false)
      es.close()
      esRef.current = null
    })

    es.onerror = () => {
      setStreaming(false)
      setError({ code: 'STREAM_ERROR', message: 'Lost connection to AI service' })
      es.close()
      esRef.current = null
    }
  }, [experimentId])

  return { text, streaming, error, startStream, stop }
}
