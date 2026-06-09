import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { BarChart2, CheckCircle2, UploadCloud } from "lucide-react"

const API_BASE = "http://localhost:8000"

// ── Hero ──────────────────────────────────────────────────────────────────────

function TrustDot({ color }) {
  return (
    <span
      style={{
        width: 6,
        height: 6,
        borderRadius: "50%",
        backgroundColor: color,
        display: "inline-block",
        flexShrink: 0,
      }}
    />
  )
}

function HeroSection() {
  return (
    <section style={{ padding: "100px 24px 80px" }}>
      <div style={{ maxWidth: 640, margin: "0 auto" }}>
        {/* Logo line */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            marginBottom: 28,
          }}
        >
          <span
            className="font-display font-bold"
            style={{ fontSize: 32, color: "var(--color-text-primary)" }}
          >
            Axiom
          </span>
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              backgroundColor: "var(--color-accent-blue)",
              display: "inline-block",
            }}
          />
        </div>

        {/* Headline */}
        <h1
          className="font-display font-bold"
          style={{
            fontSize: "clamp(36px, 5vw, 52px)",
            lineHeight: 1.1,
            color: "var(--color-text-primary)",
            margin: "0 0 20px",
          }}
        >
          Run experiments that
          <br />
          <span style={{ color: "var(--color-accent-blue)" }}>
            actually tell the truth.
          </span>
        </h1>

        {/* Subheadline */}
        <p
          style={{
            fontSize: 13,
            color: "var(--color-text-secondary)",
            maxWidth: 480,
            lineHeight: 1.7,
            marginBottom: 32,
          }}
        >
          Axiom combines statistical rigour, ML-powered analysis, and
          plain-English explanations — so anyone can run an A/B test and trust
          the result.
        </p>

        {/* Buttons */}
        <div
          style={{
            display: "flex",
            gap: 12,
            flexWrap: "wrap",
            marginBottom: 36,
          }}
        >
          <Link
            to="/experiments"
            style={{
              display: "inline-flex",
              alignItems: "center",
              padding: "10px 20px",
              borderRadius: 8,
              backgroundColor: "var(--color-accent-blue)",
              color: "white",
              fontSize: 14,
              fontWeight: 500,
              textDecoration: "none",
            }}
          >
            View Experiments →
          </Link>
          <Link
            to="/experiments/new"
            style={{
              display: "inline-flex",
              alignItems: "center",
              padding: "10px 20px",
              borderRadius: 8,
              border: "1px solid var(--color-border-subtle)",
              backgroundColor: "var(--color-bg-card)",
              color: "var(--color-text-secondary)",
              fontSize: 14,
              fontWeight: 500,
              textDecoration: "none",
            }}
          >
            Create New Experiment
          </Link>
        </div>

        {/* Trust signals */}
        <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
          {[
            { text: "430 statistical tests", color: "var(--color-accent-green)" },
            { text: "85% ML coverage",       color: "var(--color-accent-blue)" },
            { text: "Powered by Claude",      color: "var(--color-accent-amber)" },
          ].map(({ text, color }) => (
            <div key={text} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <TrustDot color={color} />
              <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                {text}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ── How It Works ──────────────────────────────────────────────────────────────

const STEPS = [
  {
    Icon: UploadCloud,
    color: "var(--color-accent-blue)",
    title: "Upload your data",
    body:
      "Bring a CSV with your experiment results. Axiom validates it client-side before anything is sent — no wasted calls, no confusing errors.",
  },
  {
    Icon: BarChart2,
    color: "var(--color-accent-green)",
    title: "Run the full pipeline",
    body:
      "Seven statistical techniques and four ML modules run automatically. Power analysis, CUPED variance reduction, HTE, segment discovery — all explained in plain English.",
  },
  {
    Icon: CheckCircle2,
    color: "var(--color-accent-amber)",
    title: "Get the story, not just numbers",
    body:
      "Every result comes with a five-act narrative: was the experiment valid, was the result real, who did it help, is the effect stable, should you ship?",
  },
]

function HowItWorksSection() {
  return (
    <section
      style={{
        padding: "80px 24px",
        borderTop: "1px solid var(--color-border-subtle)",
      }}
    >
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <p
          style={{
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: "0.15em",
            color: "var(--color-text-muted)",
            marginBottom: 40,
          }}
        >
          HOW IT WORKS
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {STEPS.map(({ Icon, color, title, body }) => (
            <div
              key={title}
              style={{
                background: "var(--color-bg-card)",
                border: "1px solid var(--color-border-subtle)",
                borderRadius: 12,
                padding: 24,
              }}
            >
              <Icon size={24} style={{ color, marginBottom: 16, display: "block" }} />
              <h3
                className="font-display"
                style={{
                  fontSize: 16,
                  fontWeight: 600,
                  color: "var(--color-text-primary)",
                  marginBottom: 10,
                }}
              >
                {title}
              </h3>
              <p
                style={{
                  fontSize: 13,
                  color: "var(--color-text-secondary)",
                  lineHeight: 1.7,
                  margin: 0,
                }}
              >
                {body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ── Live Experiments ──────────────────────────────────────────────────────────

function ExperimentCardSkeleton() {
  return (
    <div
      className="animate-pulse"
      style={{
        background: "var(--color-bg-card)",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: 12,
        padding: 24,
      }}
    >
      <div
        style={{
          height: 18,
          width: "60%",
          background: "var(--color-bg-elevated)",
          borderRadius: 4,
          marginBottom: 12,
        }}
      />
      <div
        style={{
          height: 13,
          width: "90%",
          background: "var(--color-bg-elevated)",
          borderRadius: 4,
          marginBottom: 6,
        }}
      />
      <div
        style={{
          height: 13,
          width: "70%",
          background: "var(--color-bg-elevated)",
          borderRadius: 4,
          marginBottom: 20,
        }}
      />
      <div
        style={{
          height: 24,
          width: "45%",
          background: "var(--color-bg-elevated)",
          borderRadius: 4,
        }}
      />
    </div>
  )
}

function ExperimentCard({ exp }) {
  return (
    <Link to={`/experiments/${exp.id}`} style={{ textDecoration: "none", display: "block" }}>
      <div
        style={{
          background: "var(--color-bg-card)",
          border: "1px solid var(--color-border-subtle)",
          borderRadius: 12,
          padding: 24,
          transition: "border-color 0.15s",
          height: "100%",
          boxSizing: "border-box",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = "var(--color-border-active)"
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = "var(--color-border-subtle)"
        }}
      >
        <h3
          style={{
            fontSize: 15,
            fontWeight: 500,
            color: "var(--color-text-primary)",
            marginBottom: 8,
          }}
        >
          {exp.name}
        </h3>

        {exp.description && (
          <p
            style={{
              fontSize: 13,
              color: "var(--color-text-muted)",
              marginBottom: 16,
              overflow: "hidden",
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              lineHeight: 1.5,
            }}
          >
            {exp.description}
          </p>
        )}

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            flexWrap: "wrap",
            marginBottom: 16,
          }}
        >
          {/* Status */}
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            {exp.status === "running" && (
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  backgroundColor: "var(--color-accent-green)",
                  display: "inline-block",
                }}
              />
            )}
            <span
              style={{
                fontSize: 11,
                color: "var(--color-text-muted)",
                textTransform: "capitalize",
              }}
            >
              {exp.status}
            </span>
          </div>

          {/* Type badge */}
          <span
            style={{
              fontSize: 11,
              padding: "1px 7px",
              borderRadius: 4,
              background: "rgba(59,130,246,0.10)",
              color: "var(--color-accent-blue)",
              fontFamily: "DM Mono, monospace",
            }}
          >
            {exp.experiment_type}
          </span>
        </div>

        <span style={{ fontSize: 12, color: "var(--color-accent-blue)" }}>
          View Analysis →
        </span>
      </div>
    </Link>
  )
}

function LiveExperimentsSection() {
  const [experiments, setExperiments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/experiments`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((body) => {
        setExperiments(
  (body.data ?? [])
    .sort((a, b) =>
      a.status === 'running' && b.status !== 'running' ? -1 :
      b.status === 'running' && a.status !== 'running' ? 1 : 0
    )
    .slice(0, 3)
)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  return (
    <section
      style={{
        padding: "80px 24px",
        borderTop: "1px solid var(--color-border-subtle)",
      }}
    >
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <p
          style={{
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: "0.15em",
            color: "var(--color-text-muted)",
            marginBottom: 12,
          }}
        >
          LIVE EXPERIMENTS
        </p>
        <p
          style={{
            fontSize: 14,
            color: "var(--color-text-secondary)",
            marginBottom: 32,
          }}
        >
          These are real experiments running in Axiom right now. Click any to
          see the full analysis.
        </p>

        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[0, 1, 2].map((i) => (
              <ExperimentCardSkeleton key={i} />
            ))}
          </div>
        )}

        {error && !loading && (
          <p style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
            Could not load experiments. Make sure the backend is running.
          </p>
        )}

        {!loading && !error && experiments.length === 0 && (
          <div style={{ textAlign: "center", padding: "40px 0" }}>
            <p
              style={{
                fontSize: 14,
                color: "var(--color-text-muted)",
                marginBottom: 16,
              }}
            >
              No experiments yet. Create your first one.
            </p>
            <Link
              to="/experiments/new"
              style={{
                fontSize: 14,
                color: "var(--color-accent-blue)",
                textDecoration: "none",
              }}
            >
              Create experiment →
            </Link>
          </div>
        )}

        {!loading && !error && experiments.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {experiments.map((exp) => (
              <ExperimentCard key={exp.id} exp={exp} />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

// ── Footer ────────────────────────────────────────────────────────────────────

function FooterSection() {
  return (
    <footer
      style={{
        padding: "40px 24px",
        borderTop: "1px solid var(--color-border-subtle)",
        textAlign: "center",
      }}
    >
      <p style={{ fontSize: 12, color: "var(--color-text-muted)", margin: 0 }}>
        Axiom — Built with FastAPI, React, and Claude{" "}
        <span style={{ opacity: 0.4 }}>·</span>{" "}
        <a
          href="https://github.com/anika0273/axiom"
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "var(--color-text-muted)", textDecoration: "none" }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = "var(--color-text-secondary)"
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = "var(--color-text-muted)"
          }}
        >
          GitHub ↗
        </a>
      </p>
    </footer>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Home() {
  useEffect(() => {
    document.title = "Axiom — Experimentation Platform"
    return () => {
      document.title = "Axiom"
    }
  }, [])

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "var(--color-bg-deep)",
      }}
    >
      <HeroSection />
      <HowItWorksSection />
      <LiveExperimentsSection />
      <FooterSection />
    </div>
  )
}
