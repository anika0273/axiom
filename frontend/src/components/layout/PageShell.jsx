import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import Sidebar from './Sidebar'

/**
 * @typedef {{ label: string, href?: string }} Breadcrumb
 */

/**
 * Root page wrapper — sidebar + top bar + scrollable content area.
 * @param {Object} props
 * @param {React.ReactNode} props.children
 * @param {Breadcrumb[]} [props.breadcrumbs=[]]
 * @param {React.ReactNode} [props.actions] - Buttons shown in the top-right of the top bar
 */
export default function PageShell({ children, breadcrumbs = [], actions }) {
  const hasTopBar = breadcrumbs.length > 0 || actions

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
                <nav className="flex items-center gap-1 text-sm text-muted min-w-0">
                  {breadcrumbs.map((crumb, i) => (
                    <span key={i} className="flex items-center gap-1 min-w-0">
                      {i > 0 && <ChevronRight size={13} className="flex-shrink-0 opacity-40" />}
                      {crumb.href && i < breadcrumbs.length - 1 ? (
                        <Link
                          to={crumb.href}
                          className="hover:text-primary transition-colors truncate"
                        >
                          {crumb.label}
                        </Link>
                      ) : (
                        <span className={i === breadcrumbs.length - 1 ? 'text-primary font-medium truncate' : 'truncate'}>
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
    </div>
  )
}
