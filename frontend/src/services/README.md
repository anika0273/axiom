# src/services

Typed API client functions. All HTTP calls originate here.

- One file per backend resource: `experimentsApi.ts`, `metricsApi.ts`, `reportsApi.ts`
- Functions accept typed request params and return typed response objects
- Base URL and auth headers are configured once in `apiClient.ts` (axios instance)
- No UI logic, no React imports

Components and pages never import `axios` directly — they go through these functions.
