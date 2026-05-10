import { useEffect, useRef } from 'react'
import { X, Keyboard } from 'lucide-react'

const SHORTCUTS = [
  { keys: ['N'], description: 'New experiment', context: 'Global' },
  { keys: ['/'], description: 'Focus search', context: 'Experiments list' },
  { keys: ['?'], description: 'Show this help', context: 'Global' },
  { keys: ['Esc'], description: 'Close modal / panel', context: 'Global' },
]

/**
 * Modal overlay listing all global keyboard shortcuts.
 * Closes on Escape or clicking the backdrop.
 *
 * @param {Object} props
 * @param {() => void} props.onClose
 */
export default function KeyboardShortcutsModal({ onClose }) {
  const overlayRef = useRef(null)

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  // Prevent body scroll while open
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.72)' }}
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
    >
      <div
        className="rounded-xl border border-subtle shadow-elevated w-full max-w-sm"
        style={{ backgroundColor: 'var(--color-bg-card)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-subtle">
          <div className="flex items-center gap-2">
            <Keyboard size={14} style={{ color: 'var(--color-text-muted)' }} />
            <span
              className="font-display font-bold text-sm"
              style={{ color: 'var(--color-text-primary)' }}
            >
              Keyboard shortcuts
            </span>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 transition-colors hover:bg-hover"
            style={{ color: 'var(--color-text-muted)' }}
            aria-label="Close keyboard shortcuts"
          >
            <X size={14} />
          </button>
        </div>

        {/* Shortcut list */}
        <div className="px-5 py-4 space-y-1">
          {SHORTCUTS.map(({ keys, description, context }) => (
            <div
              key={keys.join('+')}
              className="flex items-center justify-between py-2"
            >
              <div>
                <span
                  className="text-sm"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {description}
                </span>
                <span
                  className="ml-2 text-[11px]"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  {context}
                </span>
              </div>

              <div className="flex items-center gap-1 ml-4 flex-shrink-0">
                {keys.map((k) => (
                  <kbd
                    key={k}
                    className="inline-flex items-center justify-center min-w-[26px] h-[22px] px-1.5 rounded text-[11px] font-mono font-medium"
                    style={{
                      backgroundColor: 'var(--color-bg-elevated)',
                      border: '1px solid var(--color-border-subtle)',
                      color: 'var(--color-text-secondary)',
                    }}
                  >
                    {k}
                  </kbd>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer hint */}
        <div className="px-5 pb-4">
          <p
            className="text-[11px] pt-3 border-t border-subtle"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Shortcuts are disabled when focus is inside a text input.
          </p>
        </div>
      </div>
    </div>
  )
}
