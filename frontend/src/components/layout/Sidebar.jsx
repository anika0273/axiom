import { NavLink } from 'react-router-dom'
import { Home, FlaskConical, Sparkles, Plus, Zap } from 'lucide-react'

const NAV_ITEMS = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/experiments', label: 'Experiments', icon: FlaskConical },
  { to: '/demo', label: 'Demo', icon: Sparkles },
]

function NavItem({ to, label, icon: Icon, end = false, mobile = false }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        mobile
          ? [
              'flex flex-col items-center gap-0.5 px-4 py-1.5 text-[10px] font-medium transition-colors duration-100',
              isActive ? 'text-blue' : 'text-muted hover:text-secondary',
            ].join(' ')
          : [
              'flex items-center gap-3 px-3 py-2 rounded-md mx-2 text-sm font-medium transition-all duration-100',
              'border-l-2',
              isActive
                ? 'border-blue bg-elevated text-primary'
                : 'border-transparent text-secondary hover:text-primary hover:bg-hover',
            ].join(' ')
      }
    >
      <Icon size={mobile ? 20 : 18} strokeWidth={1.75} />
      <span>{label}</span>
    </NavLink>
  )
}

/**
 * Persistent left sidebar (desktop) that collapses to a bottom nav bar on mobile.
 */
export default function Sidebar() {
  return (
    <>
      {/* ── Desktop sidebar ─────────────────────────────── */}
      <aside className="hidden md:flex fixed left-0 top-0 h-screen w-sidebar flex-col border-r border-subtle bg-card z-40">
        {/* Logo */}
        <div className="flex items-center gap-2 px-5 h-14 border-b border-subtle flex-shrink-0">
          <span className="font-display font-bold text-lg text-primary tracking-tight">
            Axiom
          </span>
          <span
            className="w-1.5 h-1.5 rounded-full bg-blue flex-shrink-0"
            style={{ boxShadow: '0 0 6px var(--color-accent-blue)' }}
          />
        </div>

        {/* New Experiment CTA */}
        <div className="px-4 pt-4 pb-2">
          <NavLink
            to="/experiments/new"
            className="flex items-center gap-2 w-full px-3 py-2 rounded-md text-sm font-medium bg-blue text-white hover:brightness-110 transition-all shadow-glow"
          >
            <Plus size={16} strokeWidth={2.5} />
            New Experiment
          </NavLink>
        </div>

        {/* Nav links */}
        <nav className="flex-1 flex flex-col gap-0.5 pt-2 overflow-y-auto">
          {NAV_ITEMS.map((item) => (
            <NavItem key={item.to} {...item} />
          ))}
        </nav>

        {/* Bottom — Claude attribution */}
        <div className="flex-shrink-0 border-t border-subtle px-5 py-4">
          <div className="flex items-center gap-2 text-muted">
            <Zap size={13} className="text-blue opacity-70 flex-shrink-0" />
            <div className="leading-tight">
              <p className="text-[11px] font-medium text-secondary">Powered by Claude</p>
              <p className="text-[10px] text-muted">by Anthropic</p>
            </div>
          </div>
        </div>
      </aside>

      {/* ── Mobile bottom nav ───────────────────────────── */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 h-16 border-t border-subtle bg-card flex items-center justify-around px-2">
        {NAV_ITEMS.map((item) => (
          <NavItem key={item.to} {...item} mobile />
        ))}
        <NavLink
          to="/experiments/new"
          className={({ isActive }) =>
            [
              'flex flex-col items-center gap-0.5 px-4 py-1.5 text-[10px] font-medium transition-colors duration-100',
              isActive ? 'text-blue' : 'text-muted hover:text-secondary',
            ].join(' ')
          }
        >
          <Plus size={20} strokeWidth={1.75} />
          <span>New</span>
        </NavLink>
      </nav>
    </>
  )
}
