import { Link } from 'react-router-dom'
import { ArrowRight, FlaskConical, Zap, ShieldCheck } from 'lucide-react'

export default function HeroSection() {
  function scrollToDemos() {
    document.getElementById('demos')?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <section
      className="relative min-h-screen flex flex-col justify-center overflow-hidden"
      style={{
        background:
          'linear-gradient(160deg, #0A0E1A 0%, #0D1628 55%, #0A1220 100%)',
      }}
    >
      {/* Grid pattern overlay */}
      <div
        className="absolute inset-0 pointer-events-none select-none"
        style={{
          backgroundImage:
            'linear-gradient(rgba(59,130,246,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(59,130,246,0.035) 1px, transparent 1px)',
          backgroundSize: '60px 60px',
        }}
      />

      {/* Radial glow — centre */}
      <div
        className="absolute pointer-events-none"
        style={{
          width: 900,
          height: 600,
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          background:
            'radial-gradient(ellipse at center, rgba(59,130,246,0.07) 0%, transparent 70%)',
        }}
      />

      {/* Content */}
      <div className="relative max-w-content mx-auto px-6 py-28 text-center">
        {/* Eyebrow */}
        <p
          className="text-[11px] font-bold uppercase mb-7 tracking-[0.18em]"
          style={{ color: 'var(--color-accent-blue)' }}
        >
          Intelligent Experimentation
        </p>

        {/* Heading */}
        <h1
          className="font-display font-bold mb-7"
          style={{ fontSize: 'clamp(38px, 5vw, 56px)', lineHeight: 1.1 }}
        >
          <span style={{ color: 'var(--color-text-primary)' }}>
            Rigorous experiments.
          </span>
          <br />
          <span style={{ color: 'var(--color-text-secondary)' }}>
            No PhD required.
          </span>
        </h1>

        {/* Subheading */}
        <p
          className="text-[17px] max-w-xl mx-auto mb-11 leading-relaxed"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          Axiom combines statistical rigor, ML-powered analysis, and Claude AI
          to help product teams run experiments that actually tell the truth.
        </p>

        {/* CTAs */}
        <div className="flex flex-wrap items-center justify-center gap-4 mb-11">
          <button
            onClick={scrollToDemos}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-md text-sm font-medium text-white transition-all duration-150 hover:brightness-110"
            style={{
              backgroundColor: 'var(--color-accent-blue)',
              boxShadow: '0 0 24px rgba(59,130,246,0.35)',
            }}
          >
            Try a Demo
            <ArrowRight size={15} />
          </button>

          <Link
            to="/experiments/new"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-md text-sm font-medium transition-all duration-150 hover:border-active hover:bg-hover"
            style={{
              color: 'var(--color-text-primary)',
              border: '1px solid var(--color-border-subtle)',
              backgroundColor: 'rgba(26,34,52,0.6)',
            }}
          >
            New Experiment
          </Link>
        </div>

        {/* Trust indicators */}
        <div
          className="flex flex-wrap items-center justify-center gap-5 text-[11px]"
          style={{ color: 'var(--color-text-muted)' }}
        >
          <span className="flex items-center gap-1.5">
            <ShieldCheck size={12} style={{ color: 'var(--color-accent-green)' }} />
            430 statistical tests
          </span>
          <span className="opacity-30">·</span>
          <span className="flex items-center gap-1.5">
            <Zap size={12} style={{ color: 'var(--color-accent-amber)' }} />
            96% ML coverage
          </span>
          <span className="opacity-30">·</span>
          <span className="flex items-center gap-1.5">
            <FlaskConical size={12} style={{ color: 'var(--color-accent-blue)' }} />
            Powered by Claude
          </span>
        </div>
      </div>

      {/* Bottom fade into next section */}
      <div
        className="absolute bottom-0 left-0 right-0 h-24 pointer-events-none"
        style={{
          background:
            'linear-gradient(to bottom, transparent, #0F1724)',
        }}
      />
    </section>
  )
}
