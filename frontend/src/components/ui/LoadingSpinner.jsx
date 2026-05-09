/**
 * Thin-ring loading spinner in electric blue.
 * @param {Object} props
 * @param {number} [props.size=20] - Diameter in pixels (20, 24, or 32 recommended)
 * @param {string} [props.className]
 */
export default function LoadingSpinner({ size = 20, className = '' }) {
  const borderWidth = size <= 16 ? 2 : size <= 24 ? 2 : 3

  return (
    <span
      className={`inline-block animate-spin rounded-full border-blue ${className}`}
      style={{
        width: size,
        height: size,
        borderWidth,
        borderStyle: 'solid',
        borderTopColor: 'transparent',
        flexShrink: 0,
      }}
      aria-label="Loading"
      role="status"
    />
  )
}
