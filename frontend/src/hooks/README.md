# src/hooks

Custom React hooks for data fetching and shared stateful logic.

Convention:
- Data-fetching hooks are named `use<Resource>` (e.g. `useExperiment`, `useMetrics`)
- They call functions from `src/services/` and return `{ data, isLoading, error }`
- Side-effect hooks (e.g. `useWebSocket`, `usePolling`) live here too
- No JSX in hooks
