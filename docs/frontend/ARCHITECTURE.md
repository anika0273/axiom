# Frontend Architecture

## Overview

The Axiom frontend is a React 18 single-page application built with Vite, Tailwind CSS, and Recharts. It provides six main views: a marketing home page, an experiment list with search/filter/sort, a multi-step wizard for creating experiments, a results dashboard with charts and AI interpretation, a stakeholder report generator, and a pre-loaded demo mode that requires no backend. All pages are route-split at load time via `React.lazy`, so Recharts and other heavy dependencies only land in the browser when the relevant route is first visited.

---

## Component Hierarchy

```
App
└── RouterProvider (router.jsx)
    └── Suspense + PageFallback (spinner)
        ├── Home                           (/pages/Home.jsx)
        │   ├── HeroSection
        │   ├── ProblemSection
        │   ├── HowItWorksSection
        │   └── SampleCard (×3 demo datasets)
        │
        ├── ExperimentList                 (/pages/ExperimentList.jsx)
        │   ├── PageShell
        │   │   └── Sidebar
        │   ├── FilterTabs
        │   ├── SortDropdown
        │   ├── ExperimentRow (×N)
        │   │   ├── Badge
        │   │   └── LiftBadge
        │   └── Pagination
        │
        ├── NewExperiment (wizard)         (/pages/NewExperiment.jsx)
        │   ├── PageShell
        │   ├── WizardProgress
        │   ├── Step1Describe → Step2Metrics → Step3Settings
        │   ├── AIPlanPanel   (AI planning, fires useExperimentPlan)
        │   └── SummaryPanel
        │
        ├── ExperimentResults              (/pages/ExperimentResults.jsx)
        │   ├── PageShell
        │   ├── VerdictBanner
        │   ├── MetricsRow
        │   ├── MetricComparisonChart (memo)
        │   ├── SequentialChart (memo)
        │   ├── SegmentTable (memo)
        │   ├── AnomalyFlags
        │   ├── NoveltyPanel
        │   └── AIInterpretationPanel  (fires useStreamingInterpretation)
        │
        ├── StakeholderReport              (/pages/StakeholderReport.jsx)
        │   ├── PageShell
        │   ├── ReportHeader
        │   ├── GeneratingProgress
        │   ├── RecommendationBadge
        │   ├── ReportSection (×8)
        │   └── ReportActions
        │
        ├── Demo                           (/pages/Demo.jsx)
        │   └── SampleCard (×3, links to /demo/:name)
        │
        └── DemoExperimentResults          (/pages/DemoExperimentResults.jsx)
            └── (same shape as ExperimentResults, uses local JSON)
```

### Layout shell

`PageShell` wraps every authenticated page. It renders `Sidebar` on the left, a sticky breadcrumb/actions top bar, and a `<main>` content area. It also registers global keyboard shortcuts (`N` → new experiment, `/` → focus search, `?` → shortcuts modal).

```jsx
<PageShell
  breadcrumbs={[{ label: 'Experiments', href: '/experiments' }, { label: exp.name }]}
  actions={<Button size="sm">Export</Button>}
>
  {/* page content */}
</PageShell>
```

---

## State Management

State is kept as local as possible and never duplicated.

| Type | Where | Examples |
|---|---|---|
| Server data | Custom hooks (`useAPI`, `useStreamingReport`) | experiment list, results, report |
| Streaming text | `useStreamingInterpretation`, `useStreamingReport` | AI interpretation, report generation |
| Wizard state | `NewExperiment` useState + passed down as props | currentStep, formData |
| UI-local state | Individual components | expanded sections, copied-to-clipboard flag, modal open |
| Persisted local | `useLocalStorage` | wizard draft (survives page refresh) |

There is no global store (no Zustand, no Redux). The wizard is the most complex stateful flow — `NewExperiment` owns all step data in a single `formData` object and passes `onChange` callbacks down to each step component. This keeps the wizard's state in one place and makes reset trivial.

---

## Data Fetching Strategy

### `useAPI` — standard REST fetching

```js
const { data, loading, error, refetch } = useAPI('/api/v1/experiments/123')
```

Return shape is always `{ data, loading, isSlowRequest, error, refetch }`. `data` is `null` until the request resolves. `error` is `{ message, status, code, errorType }` where `errorType` is one of `'network'`, `'not_found'`, `'server_error'`, or `'api_error'`.

The hook aborts in-flight requests when the `url` prop changes (via `AbortController`) and marks `isSlowRequest = true` after 10 seconds — pages can surface a "this is taking longer than usual" message without triggering a full error state.

### Demo mode — pre-computed local JSON

`DemoExperimentResults` and `Demo` load data from `src/data/samples/*.json` (ecommerce, saas, marketplace). These are pre-computed result objects that match the live API shape exactly. No API calls are made in demo mode — the component imports the JSON directly and passes it through the same `buildResult()` helper that live pages use.

### No client-side cache

There is no SWR/React Query layer. Each page fetches fresh on mount. For the experiment list, all experiments are fetched in a single call (up to 200) and all filtering/sorting/pagination happens client-side in `useMemo`.

---

## Streaming (SSE)

### AI interpretation — `useStreamingInterpretation`

Opens an `EventSource` to `GET /api/v1/intelligence/experiments/:id/interpret`. The backend streams JSON-encoded chunks; the hook appends each chunk's `.text` field to a `text` string in state. When the server sends `[DONE]` or the `done` event, streaming stops.

```js
const { text, streaming, startStream, stop } = useStreamingInterpretation(experimentId)

// Start on user click:
<Button onClick={startStream}>Interpret results</Button>

// Render progressively:
<p style={{ whiteSpace: 'pre-wrap' }}>{text}</p>
```

### Stakeholder report — `useStreamingReport`

The report endpoint is a regular `POST` (not SSE) because it uses Claude tool_use, which can't stream incrementally. `useStreamingReport` simulates progress by advancing a section counter every 1.8 seconds while the fetch is in flight. On response, it maps the returned sections object to the `GeneratingProgress` and `ReportSection` components.

---

## Design Token System

All colours and the font stack are defined as CSS custom properties in `src/index.css`. Tailwind utility classes reference them via arbitrary-value syntax where needed (e.g. `bg-[var(--color-bg-elevated)]`), but most components use inline `style` props for colour to avoid Tailwind purging dynamic values.

| Variable | Value | Purpose |
|---|---|---|
| `--color-bg-deep` | `#0A0E1A` | Page background (deepest) |
| `--color-bg-card` | `#111827` | Card / panel surface |
| `--color-bg-elevated` | `#1A2234` | Elevated surface (table headers, dropdowns) |
| `--color-bg-hover` | `#1E2D3D` | Hover state background |
| `--color-border-subtle` | `#1E2D40` | Default border |
| `--color-border-active` | `#2A4A6B` | Focused / active border |
| `--color-accent-blue` | `#3B82F6` | Primary action, data highlight |
| `--color-accent-blue-dim` | `#1D4ED8` | Text selection background |
| `--color-accent-green` | `#10B981` | Significant / positive |
| `--color-accent-amber` | `#F59E0B` | Warning / not-yet-significant |
| `--color-accent-red` | `#EF4444` | Danger / negative lift |
| `--color-text-primary` | `#F1F5F9` | Body text |
| `--color-text-secondary` | `#94A3B8` | Secondary labels |
| `--color-text-muted` | `#475569` | Placeholder, empty states |
| `--color-text-data` | `#60A5FA` | Inline data values, metric names |

**Fonts:**
- `'Syne'` — headings (`h1`–`h6`, `.font-display`)
- `'DM Mono'` — numeric data, code, axis labels (`.font-mono`)
- `'DM Sans'` — body text (default)

Fonts are loaded from Google Fonts via `@import` in `index.css`. `index.html` includes `<link rel="preconnect">` and `<link rel="preload">` tags to discover them before CSS is parsed.

---

## How to Add a New Page

**1. Create the page component**

```jsx
// src/pages/MyPage.jsx
import { useAPI } from '../hooks/useAPI'
import PageShell from '../components/layout/PageShell'
import NetworkError from '../components/errors/NetworkError'
import Skeleton from '../components/ui/Skeleton'

export default function MyPage() {
  const { data, loading, error, refetch } = useAPI('/api/v1/my-resource')

  if (error?.errorType === 'network') return <NetworkError onRetry={refetch} />
  if (error) return <APIError message={error.message} onRetry={refetch} />

  return (
    <PageShell breadcrumbs={[{ label: 'My Page' }]}>
      {loading ? (
        <Skeleton variant="block" className="h-40" />
      ) : (
        <p style={{ color: 'var(--color-text-primary)' }}>{data?.name}</p>
      )}
    </PageShell>
  )
}
```

**2. Add the route** in `src/router.jsx`:

```js
const MyPage = lazy(() => import('./pages/MyPage'))

// inside createBrowserRouter([...]):
{
  path: '/my-page',
  element: <Suspense fallback={<PageFallback />}><MyPage /></Suspense>,
  errorElement: <RouteError />,
},
```

**3. Add a sidebar link** in `src/components/layout/Sidebar.jsx` — find the `NAV_ITEMS` array and add an entry:

```js
{ label: 'My Page', href: '/my-page', icon: MyIcon }
```

**4. (Optional)** Link from `Home.jsx` hero if it's a primary destination.

---

## How to Add a New Chart

Charts live in `src/components/charts/`. All use Recharts wrapped in `ResponsiveContainer`.

```jsx
// src/components/charts/MyChart.jsx
import { memo } from 'react'
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts'

const MyChart = memo(function MyChart({ data }) {
  if (!data?.length) return null
  return (
    <div
      className="rounded-md border border-subtle p-5"
      style={{ backgroundColor: 'var(--color-bg-card)' }}
    >
      <div style={{ height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis dataKey="day" tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }} />
            <YAxis tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }} />
            <Tooltip />
            <Line dataKey="value" stroke="var(--color-accent-blue)" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
})

export default MyChart
```

Guidelines:
- Always wrap with `memo` — chart components receive large data arrays and should not re-render from parent state churn.
- Return `null` when `data` is empty (not an empty canvas).
- Use CSS variables for all colours, never hardcoded hex.
- Border radius on the container: `rounded-md` (6 px).
