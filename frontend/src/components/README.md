# src/components

Reusable UI components shared across pages.

Organisation:
- `charts/` — Recharts wrappers (e.g. `MetricLineChart.tsx`, `ConversionFunnelChart.tsx`)
- `ui/` — Generic primitives: `Button`, `Badge`, `Card`, `Modal`, `Tooltip`
- `experiments/` — Domain-specific components: `ExperimentCard`, `VariantTable`, `StatsSummary`

Rules:
- Props interfaces are defined immediately above the component they belong to
- No API calls inside components — use hooks from `src/hooks/` instead
- No direct Tailwind arbitrary values — use the design token scale
