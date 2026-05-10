import { Check, Loader } from 'lucide-react'

/**
 * Progress tracker shown while the report is being generated.
 * Each section transitions: pending → writing (animated) → complete.
 *
 * @param {Object} props
 * @param {number} props.currentSection  - 0-based index of section currently being written
 * @param {number} props.totalSections   - Total section count (always 8)
 * @param {string} props.sectionName     - Name of the section currently being written
 * @param {string[]} props.sectionNames  - All section names in order
 * @param {boolean} props.longRunning    - True after 30s — shows "Still working…"
 */
export default function GeneratingProgress({
  currentSection,
  totalSections,
  sectionName,
  sectionNames,
  longRunning,
}) {
  return (
    <div className="flex flex-col items-center py-16 px-4">
      {/* Typing indicator */}
      <div className="flex items-center gap-1.5 mb-8">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="inline-block w-2 h-2 rounded-full animate-pulse"
            style={{
              backgroundColor: 'var(--color-accent-blue)',
              animationDelay: `${i * 180}ms`,
            }}
          />
        ))}
      </div>

      {/* Status text */}
      <p
        className="font-display font-semibold text-base mb-1"
        style={{ color: 'var(--color-text-primary)' }}
      >
        {longRunning
          ? 'Still working…'
          : `Writing section ${Math.min(currentSection + 1, totalSections)} of ${totalSections}…`}
      </p>
      {sectionName && !longRunning && (
        <p
          className="text-sm mb-10"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {sectionName}
        </p>
      )}
      {longRunning && (
        <p
          className="text-sm mb-10"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Claude is still generating — this can take up to 60 seconds.
        </p>
      )}

      {/* Section checklist */}
      <div className="w-full max-w-xs space-y-2">
        {sectionNames.map((name, i) => {
          const isComplete = i < currentSection
          const isActive = i === currentSection
          const isPending = i > currentSection

          return (
            <div
              key={name}
              className="flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-300"
              style={{
                backgroundColor: isActive
                  ? 'rgba(59,130,246,0.08)'
                  : 'transparent',
              }}
            >
              {/* State icon */}
              <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center">
                {isComplete ? (
                  <Check
                    size={14}
                    strokeWidth={2.5}
                    style={{ color: 'var(--color-accent-green)' }}
                  />
                ) : isActive ? (
                  <Loader
                    size={14}
                    className="animate-spin"
                    style={{ color: 'var(--color-accent-blue)' }}
                  />
                ) : (
                  <span
                    className="w-3 h-3 rounded border-2 inline-block"
                    style={{ borderColor: 'var(--color-border-subtle)' }}
                  />
                )}
              </span>

              {/* Section name */}
              <span
                className="text-sm"
                style={{
                  color: isComplete
                    ? 'var(--color-accent-green)'
                    : isActive
                    ? 'var(--color-text-primary)'
                    : 'var(--color-text-muted)',
                  fontWeight: isActive ? 600 : 400,
                }}
              >
                {name}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
