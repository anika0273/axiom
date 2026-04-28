# src/pages

Route-level page components, one file per route.

Planned pages:
- `DashboardPage.tsx` — Overview of all experiments and key metrics
- `ExperimentListPage.tsx` — Filterable/sortable list of experiments
- `ExperimentDetailPage.tsx` — Live stats, charts, and AI summary for one experiment
- `NewExperimentPage.tsx` — Wizard to create and configure a new experiment
- `ReportPage.tsx` — Full post-experiment report with AI narrative

Each page is responsible for composing components and triggering data fetches via hooks.
Pages should not contain inline business logic — extract to hooks or services.
