import { useState, useEffect } from 'react'

/**
 * State hook synced to localStorage. Falls back to `defaultValue` if the key
 * is absent or if JSON parsing fails.
 *
 * @template T
 * @param {string} key - localStorage key
 * @param {T} defaultValue
 * @returns {[T, (value: T | ((prev: T) => T)) => void]}
 */
export function useLocalStorage(key, defaultValue) {
  const [value, setValue] = useState(() => {
    try {
      const stored = localStorage.getItem(key)
      return stored !== null ? JSON.parse(stored) : defaultValue
    } catch {
      return defaultValue
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value))
    } catch {
      // Quota exceeded or private browsing — fail silently
    }
  }, [key, value])

  return [value, setValue]
}
