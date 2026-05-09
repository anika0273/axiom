import { useState, useCallback } from 'react'
import axios from 'axios'

export function useExperimentPlan() {
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [questions, setQuestions] = useState([])

  const planExperiment = useCallback(async (description) => {
    if (!description.trim()) return null

    setLoading(true)
    setError(null)
    setPlan(null)
    setQuestions([])

    try {
      const res = await axios.post('/api/v1/intelligence/plan', { description })
      const result = res.data

      if (result.needs_clarification) {
        setQuestions(result.clarifying_questions ?? [])
        setPlan(null)
      } else {
        setPlan(result.plan)
      }
      return result
    } catch (err) {
      const apiError = err.response?.data
      const msg =
        apiError?.error?.message ??
        apiError?.detail ??
        err.message ??
        'Planning failed. Try a more detailed description.'
      setError(msg)
      const clarifying = apiError?.clarifying_questions ?? []
      if (clarifying.length) setQuestions(clarifying)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setPlan(null)
    setError(null)
    setQuestions([])
  }, [])

  return { plan, loading, error, questions, planExperiment, reset }
}
