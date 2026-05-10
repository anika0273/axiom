import { Link } from 'react-router-dom'
import {
  FlaskConical,
  CheckCircle2,
  BarChart2,
  GitBranch,
  Layers,
  Sparkles,
  ExternalLink,
} from 'lucide-react'

import HeroSection from '../components/home/HeroSection'
import ProblemSection from '../components/home/ProblemSection'
import SampleCard from '../components/home/SampleCard'
import HowItWorksSection from '../components/home/HowItWorksSection'

const DEMO_CARDS = [
  {
    slug: 'ecommerce',
    title: 'E-Commerce Checkout',
    accentColor: '#3B82F6',
    insight:
      'Catches a mobile/desktop treatment divergence that the average would have hidden — plus a broken randomisation that invalidates the headline number.',
    users: '10,000',
    metricType: 'Conversion Rate',
    verdict: 'NEEDS_REVIEW',
  },
  {
    slug: 'saas',
    title: 'SaaS Free Trial',
    accentColor: '#10B981',
    insight:
      'Shows how company size creates two completely different experiments in one: enterprises convert 8pp more, small teams see negligible change.',
    users: '5,000',
    metricType: 'Trial Conversion',
    verdict: 'SIGNIFICANT',
  },
  {
    slug: 'marketplace',
    title: 'Marketplace Fee Reduction',
    accentColor: '#F59E0B',
    insight:
      'Flags a 5× volume spike on days 8–9 before you commit to a result — and reveals the seller-tenure HTE hidden inside an inconclusive overall average.',
    users: '20,000',
    metricType: 'Gross Merch Value',
    verdict: 'NOT_SIGNIFICANT',
  },
]

const DEMO_FEATURES = [
  { Icon: BarChart2, label: 'Statistical significance verdict' },
  { Icon: Layers, label: 'Segment-level HTE analysis' },
  { Icon: GitBranch, label: 'Anomaly and novelty detection' },
  { Icon: Sparkles, label: 'AI-generated interpretation' },
  { Icon: CheckCircle2, label: 'Stakeholder report' },
]

// ─── Minimal top nav ─────────────────────────────────────────────────────────

function TopNav() {
  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 border-b backdrop-blur-md"
      style={{
        borderColor: 'rgba(30,45,64,0.7)',
        backgroundColor: 'rgba(10,14,26,0.85)',
      }}
    >
      <div className="max-w-content mx-auto px-6 h-14 flex items-center justify-between gap-4">
        {/* Logo */}
        <Link
          to="/"
          className="flex items-center gap-2 font-display font-bold text-[15px]"
          style={{ color: 'var(--color-text-primary)', textDecoration: 'none' }}
        >
          <FlaskConical size={17} style={{ color: 'var(--color-accent-blue)' }} />
          Axiom
        </Link>

        {/* Nav links */}
        <nav className="hidden sm:flex items-center gap-1">
          <Link
            to="/experiments"
            className="px-3 py-1.5 rounded-md text-sm transition-colors hover:bg-hover"
            style={{ color: 'var(--color-text-secondary)', textDecoration: 'none' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-text-primary)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-text-secondary)')}
          >
            Experiments
          </Link>
          <Link
            to="/experiments/new"
            className="ml-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all hover:brightness-110"
            style={{
              color: 'white',
              backgroundColor: 'var(--color-accent-blue)',
              textDecoration: 'none',
              boxShadow: '0 0 12px rgba(59,130,246,0.25)',
            }}
          >
            New Experiment
          </Link>
        </nav>
      </div>
    </header>
  )
}

// ─── Demo cards section ───────────────────────────────────────────────────────

function DemosSection() {
  return (
    <section
      id="demos"
      className="py-24 px-6"
      style={{ backgroundColor: '#0F1724' }}
    >
      <div className="max-w-content mx-auto">
        {/* Label */}
        <p
          className="text-[10px] font-bold uppercase tracking-[0.18em] mb-4"
          style={{ color: 'var(--color-accent-blue)' }}
        >
          Live Demos
        </p>

        {/* Heading */}
        <h2
          className="font-display font-bold mb-3"
          style={{
            fontSize: 'clamp(26px, 3.5vw, 38px)',
            color: 'var(--color-text-primary)',
          }}
        >
          Try it with real data.
        </h2>

        <p
          className="text-[15px] max-w-xl mb-12 leading-relaxed"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          Three real experimental scenarios, each showing a different way most
          A/B testing goes wrong.
        </p>

        {/* Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-12">
          {DEMO_CARDS.map((card) => (
            <SampleCard key={card.slug} {...card} />
          ))}
        </div>

        {/* Feature checklist */}
        <div
          className="rounded-lg border border-subtle p-6"
          style={{ backgroundColor: 'var(--color-bg-card)' }}
        >
          <p
            className="text-xs font-medium mb-5"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            What you'll see in each demo:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {DEMO_FEATURES.map(({ Icon, label }) => (
              <div key={label} className="flex items-center gap-2">
                <Icon
                  size={13}
                  className="flex-shrink-0"
                  style={{ color: 'var(--color-accent-blue)' }}
                />
                <span
                  className="text-[12px]"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

// ─── Footer ───────────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer
      className="border-t py-10 px-6"
      style={{
        borderColor: 'var(--color-border-subtle)',
        backgroundColor: 'var(--color-bg-deep)',
      }}
    >
      <div className="max-w-content mx-auto flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <FlaskConical size={15} style={{ color: 'var(--color-accent-blue)' }} />
          <span
            className="font-display font-bold text-sm"
            style={{ color: 'var(--color-text-primary)' }}
          >
            Axiom
          </span>
          <span
            className="text-[12px]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            · Built with FastAPI, React, and Claude
          </span>
        </div>

        <a
          href="https://github.com"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-[12px] transition-colors hover:text-primary"
          style={{ color: 'var(--color-text-muted)', textDecoration: 'none' }}
        >
          <ExternalLink size={12} />
          GitHub
        </a>
      </div>
    </footer>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function Home() {
  return (
    <div
      className="min-h-screen"
      style={{ backgroundColor: 'var(--color-bg-deep)' }}
    >
      <TopNav />

      {/* Push content below fixed nav */}
      <div className="pt-14">
        <HeroSection />
        <ProblemSection />
        <DemosSection />
        <HowItWorksSection />
        <Footer />
      </div>
    </div>
  )
}
