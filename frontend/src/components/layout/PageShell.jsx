import { useState, useEffect, useCallback } from 'react'
import { ChevronRight } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import Sidebar from './Sidebar'
import KeyboardShortcutsModal from '../KeyboardShortcutsModal'

/**
 * @typedef {{ label: string, href?: string }} Breadcrumb
 */

function isInputFocused() {
  const el = document.activeElement
  if (!el) return false
  const tag = el.tagName
  return (
    tag === 'INPUT' ||
    tag === 'TEXTAREA' ||
    tag === 'SELECT' ||
    el.contentEditable === 'true' ||
    el.isContentEditable
  )
}

/**
 * Root page wrapper — sidebar + top bar + scrollable content area.
 * Provides global keyboard shortcuts (N, /, ?, Esc).
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children
 * @param {Breadcrumb[]} [props.breadcrumbs=[]]
 * @param {React.ReactNode} [props.actions] - Buttons shown in the top-right of the top bar
 */
export default function PageShell({ children, breadcrumbs = [], actions }) {
  const hasTopBar = breadcrumbs.length > 0 || actions
  const navigate = useNavigate()
  const [showShortcuts, setShowShortcuts] = useState(false)

  const handleKeyDown = useCallback(
    (e) => {
      // Never fire shortcuts when the user is typing in an input
      if (isInputFocused()) return

      // Don't fire when modifier keys are held (let the browser handle Ctrl+N, etc.)
      if (e.metaKey || e.ctrlKey || e.altKey) return

      switch (e.key) {
        case 'n':
        case 'N':
          e.preventDefault()
          navigate('/experiments/new')
          break

        case '/':
          e.preventDefault()
          document.querySelector('[data-search-input]')?.focus()
          break

        case '?':
          e.preventDefault()
          setShowShortcuts((prev) => !prev)
          break

        case 'Escape':
          setShowShortcuts(false)
          break

        default:
          break
      }
    },
    [navigate],
  )

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      {/* Main area — offset by sidebar width on desktop, add padding-bottom on mobile for bottom nav */}
      <div className="flex-1 md:ml-sidebar max-md:pb-16 min-w-0 flex flex-col">
        {hasTopBar && (
          <header
            className="sticky top-0 z-30 border-b border-subtle backdrop-blur-md flex-shrink-0"
            style={{ backgroundColor: 'rgba(10,14,26,0.85)' }}
          >
            <div className="max-w-content mx-auto px-6 h-14 flex items-center justify-between gap-4">
              {/* Breadcrumbs */}
              {breadcrumbs.length > 0 && (
                <nav
                  className="flex items-center gap-1 text-sm text-muted min-w-0"
                  aria-label="Breadcrumb"
                >
                  {breadcrumbs.map((crumb, i) => (
                    <span key={i} className="flex items-center gap-1 min-w-0">
                      {i > 0 && (
                        <ChevronRight
                          size={13}
                          className="flex-shrink-0 opacity-40"
                          aria-hidden="true"
                        />
                      )}
                      {crumb.href && i < breadcrumbs.length - 1 ? (
                        <Link
                          to={crumb.href}
                          className="hover:text-primary transition-colors truncate"
                        >
                          {crumb.label}
                        </Link>
                      ) : (
                        <span
                          className={
                            i === breadcrumbs.length - 1
                              ? 'text-primary font-medium truncate'
                              : 'truncate'
                          }
                          aria-current={i === breadcrumbs.length - 1 ? 'page' : undefined}
                        >
                          {crumb.label}
                        </span>
                      )}
                    </span>
                  ))}
                </nav>
              )}

              {/* Page actions */}
              {actions && (
                <div className="flex items-center gap-2 flex-shrink-0 ml-auto">
                  {actions}
                </div>
              )}
            </div>
          </header>
        )}

        <main className="flex-1 max-w-content mx-auto w-full px-6 py-8">
          {children}
        </main>
      </div>

      {/* Global keyboard shortcuts modal */}
      {showShortcuts && (
        <KeyboardShortcutsModal onClose={() => setShowShortcuts(false)} />
      )}
    </div>
  )
}
