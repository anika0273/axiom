import { useState, useEffect, useCallback, useRef } from 'react'

const SLOW_REQUEST_MS = 10_000

/**
 * Data-fetching hook with loading/error states, slow-request detection, and manual refetch.
 * Automatically re-fetches when `url` changes.
 *
 * @param {string|null} url - Fetch URL. Pass null to skip the fetch.
 * @param {RequestInit} [options={}] - fetch options (method, headers, body, etc.)
 * @returns {{
 *   data: any,
 *   loading: boolean,
 *   isSlowRequest: boolean,
 *   error: {message: string, status?: number, code?: string, errorType: string}|null,
 *   refetch: () => void
 * }}
 */
export function useAPI(url, options = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(!!url)
  const [isSlowRequest, setIsSlowRequest] = useState(false)
  const [error, setError] = useState(null)
  const abortRef = useRef(null)
  const slowTimerRef = useRef(null)
  // Stable options ref so options object identity doesn't trigger re-fetches
  const optionsRef = useRef(options)
  optionsRef.current = options

  const fetchData = useCallback(async (fetchUrl) => {
    if (!fetchUrl) return

    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    // Clear any previous slow timer
    clearTimeout(slowTimerRef.current)
    setIsSlowRequest(false)

    setLoading(true)
    setError(null)

    // Mark as slow after SLOW_REQUEST_MS
    slowTimerRef.current = setTimeout(() => setIsSlowRequest(true), SLOW_REQUEST_MS)

    try {
      const res = await fetch(fetchUrl, {
        ...optionsRef.current,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...optionsRef.current.headers,
        },
      })

      if (!res.ok) {
        let errorCode = 'API_ERROR'
        try {
          const body = await res.json()
          errorCode = body?.error?.code ?? errorCode
        } catch {
          // ignore parse failure
        }
        throw Object.assign(new Error(`Request failed: ${res.statusText}`), {
          status: res.status,
          code: errorCode,
        })
      }

      const json = await res.json()
      setData(json?.data ?? json)
    } catch (err) {
      if (err.name === 'AbortError') return

      let errorType = 'api_error'
      if (!navigator.onLine) {
        errorType = 'network'
      } else if (err.status === 404) {
        errorType = 'not_found'
      } else if (err.status >= 500) {
        errorType = 'server_error'
      } else if (!err.status) {
        // No status means network-level failure
        errorType = 'network'
      }

      setError({
        message: err.message,
        status: err.status ?? null,
        code: err.code ?? 'NETWORK_ERROR',
        errorType,
      })
    } finally {
      clearTimeout(slowTimerRef.current)
      setIsSlowRequest(false)
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData(url)
    return () => {
      abortRef.current?.abort()
      clearTimeout(slowTimerRef.current)
    }
  }, [url, fetchData])

  const refetch = useCallback(() => fetchData(url), [url, fetchData])

  return { data, loading, isSlowRequest, error, refetch }
}
