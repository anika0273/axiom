import { useParams, Link } from 'react-router-dom'
import { Sparkles, ArrowRight, ShoppingCart, BarChart3, Store } from 'lucide-react'
import PageShell from '../components/layout/PageShell'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'

const DATASETS = [
  {
    name: 'ecommerce',
    title: 'E-Commerce Checkout',
    icon: ShoppingCart,
    color: 'blue',
    description:
      '50,000-user A/B test on a checkout flow redesign. Measures conversion rate, revenue per session, and cart abandonment across desktop and mobile cohorts.',
    metric: 'Checkout Conversion',
    subjects: '50,000',
    duration: '14 days',
    result: 'significant',
    lift: '+12.4%',
  },
  {
    name: 'saas',
    title: 'SaaS Onboarding',
    icon: BarChart3,
    color: 'green',
    description:
      'Trial-to-paid conversion experiment comparing a guided onboarding checklist against a free-exploration flow across 12K trial accounts.',
    metric: 'Trial → Paid Conversion',
    subjects: '12,400',
    duration: '21 days',
    result: 'significant',
    lift: '+8.9%',
  },
  {
    name: 'marketplace',
    title: 'Marketplace Listings',
    icon: Store,
    color: 'amber',
    description:
      '31K-user CTR test on listing page headline formatting and hero image placement. Includes novelty-effect correction via CUPED.',
    metric: 'Click-through Rate',
    subjects: '31,200',
    duration: '10 days',
    result: 'not-significant',
    lift: '-1.1%',
  },
]

export default function Demo() {
  const { name } = useParams()
  const active = name ? DATASETS.find(d => d.name === name) : null

  return (
    <PageShell
      breadcrumbs={
        active
          ? [{ label: 'Demo', href: '/demo' }, { label: active.title }]
          : [{ label: 'Demo' }]
      }
      actions={
        active && (
          <Link to={`/demo/${active.name}`}>
            <Button size="sm">
              <ArrowRight size={13} />
              Open Results
            </Button>
          </Link>
        )
      }
    >
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles size={16} className="text-blue" />
          <span className="text-xs text-secondary uppercase tracking-widest font-medium">
            Pre-loaded Sample Experiments
          </span>
        </div>
        <h1 className="font-display text-2xl font-bold text-primary mb-1">Demo Datasets</h1>
        <p className="text-secondary text-sm max-w-xl">
          Explore real-looking A/B experiment data to see how Axiom analyses results, detects heterogeneous
          treatment effects, and generates stakeholder reports.
        </p>
      </div>

      {/* Dataset cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
        {DATASETS.map((dataset) => {
          const Icon = dataset.icon
          const isActive = active?.name === dataset.name

          return (
            <Link key={dataset.name} to={`/demo/${dataset.name}`} className="block group">
              <Card
                variant={isActive ? 'accent' : 'default'}
                accentColor={dataset.color}
                className={`p-5 h-full transition-all duration-150 ${
                  isActive
                    ? 'border-active'
                    : 'hover:bg-elevated hover:border-active cursor-pointer'
                }`}
              >
                <div className="flex items-start justify-between mb-4">
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: `rgba(59,130,246,0.1)` }}
                  >
                    <Icon size={16} style={{ color: `var(--color-accent-${dataset.color})` }} />
                  </div>
                  <Badge variant={dataset.result} />
                </div>

                <h3 className="font-display font-bold text-[15px] text-primary mb-2 group-hover:text-data transition-colors">
                  {dataset.title}
                </h3>
                <p className="text-xs text-secondary leading-relaxed mb-4">{dataset.description}</p>

                <div className="grid grid-cols-3 gap-2 text-center border-t border-subtle pt-4">
                  <div>
                    <p className="font-mono text-sm font-medium text-primary">{dataset.lift}</p>
                    <p className="text-[10px] text-muted uppercase tracking-wide mt-0.5">Lift</p>
                  </div>
                  <div>
                    <p className="font-mono text-sm font-medium text-primary">{dataset.subjects}</p>
                    <p className="text-[10px] text-muted uppercase tracking-wide mt-0.5">Subjects</p>
                  </div>
                  <div>
                    <p className="font-mono text-sm font-medium text-primary">{dataset.duration}</p>
                    <p className="text-[10px] text-muted uppercase tracking-wide mt-0.5">Duration</p>
                  </div>
                </div>
              </Card>
            </Link>
          )
        })}
      </div>

      {/* Loaded dataset detail */}
      {active && (
        <Card variant="accent" accentColor={active.color} className="p-6 max-w-2xl">
          <h2 className="font-display font-bold text-base text-primary mb-1">
            {active.title} — loaded
          </h2>
          <p className="text-secondary text-sm mb-4">
            Click "Open Results" to explore the full analysis dashboard for this dataset, including
            heterogeneous treatment effects, segment breakdowns, and the AI stakeholder report.
          </p>
          <Link to={`/demo/${active.name}`}>
            <Button size="sm">
              Open Full Analysis <ArrowRight size={13} />
            </Button>
          </Link>
        </Card>
      )}
    </PageShell>
  )
}
