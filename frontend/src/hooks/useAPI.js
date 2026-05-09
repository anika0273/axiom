import { useState, useEffect, useCallback, useRef } from 'react'

/**
 * Data-fetching hook with loading/error states and manual refetch.
 * Automatically re-fetches when `url` changes.
 *
 * @param {string|null} url - Fetch URL. Pass null to skip the fetch.
 * @param {RequestInit} [options={}] - fetch options (method, headers, body, etc.)
 * @returns {{ data: any, loading: boolean, error: {message: string, status?: number}|null, refetch: () => void }}
 */
export function useAPI(url, options = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(!!url)
  const [error, setError] = useState(null)
  const abortRef = useRef(null)
  // Stable options ref so options object identity doesn't trigger re-fetches
  const optionsRef = useRef(options)
  optionsRef.current = options

  const fetchData = useCallback(async (fetchUrl) => {
    if (!fetchUrl) return

    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)

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
      setError({ message: err.message, status: err.status ?? null, code: err.code ?? 'NETWORK_ERROR' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData(url)
    return () => abortRef.current?.abort()
  }, [url, fetchData])

  const refetch = useCallback(() => fetchData(url), [url, fetchData])

  return { data, loading, error, refetch }
}
