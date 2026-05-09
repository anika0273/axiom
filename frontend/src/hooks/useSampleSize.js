import { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'

/**
 * Debounced sample-size + runtime calculator.
 *
 * baseline  — string like "10" meaning 10%, converted to 0.10 before API call
 * mde       — number like 5 meaning 5 pp absolute lift, converted to 0.05
 * alpha/power — already decimal (0.05, 0.80)
 * dailyTraffic — string like "500"; omit/blank to skip runtime estimate
 */
export function useSampleSize({ baseline, mde, alpha, power, dailyTraffic }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [stale, setStale] = useState(false)
  const timerRef = useRef(null)
  const abortRef = useRef(null)

  const calculate = useCallback(async (params) => {
    const { baseline, mde, alpha, power, dailyTraffic } = params

    const baselineRate = parseFloat(baseline) / 100
    const mdeDecimal = parseFloat(mde) / 100

    // Only call API when values are valid for a proportion test
    if (isNaN(baselineRate) || baselineRate <= 0 || baselineRate >= 1) return
    if (isNaN(mdeDecimal) || mdeDecimal <= 0) return

    if (abortRef.current) abortRef.current.abort()
    abortRef.current = new AbortController()
    const { signal } = abortRef.current

    setLoading(true)
    try {
      const ssRes = await axios.post(
        '/api/v1/stats/power/sample-size',
        {
          baseline_rate: baselineRate,
          mde: mdeDecimal,
          alpha: parseFloat(alpha),
          power: parseFloat(power),
        },
        { signal },
      )
      const ss = ssRes.data.data

      let runtime = null
      const trafficNum = parseInt(dailyTraffic, 10)
      if (trafficNum > 0) {
        const rtRes = await axios.post(
          '/api/v1/stats/power/runtime',
          { required_sample_size: ss.total_sample_size, daily_traffic: trafficNum },
          { signal },
        )
        runtime = rtRes.data.data
      }

      setResult({ ss, runtime })
      setError(null)
      setStale(false)
    } catch (err) {
      if (err.name === 'CanceledError' || axios.isCancel?.(err)) return
      setError(err.response?.data?.error?.message ?? err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    // Mark previous result stale immediately for optimistic display
    if (result) setStale(true)

    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      calculate({ baseline, mde, alpha, power, dailyTraffic })
    }, 300)

    return () => clearTimeout(timerRef.current)
  }, [baseline, mde, alpha, power, dailyTraffic, calculate]) // eslint-disable-line react-hooks/exhaustive-deps

  return { result, loading, error, stale }
}
