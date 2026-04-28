# src/store

Global client state managed with Zustand.

Use the store only for state that is truly global:
- Authenticated user session
- UI preferences (sidebar open/closed, theme)
- Real-time notifications

Server state (experiment data, metrics) should be managed by hooks in `src/hooks/`,
not the global store. Avoid duplicating server state here.

One Zustand store slice per concern: `useAuthStore.ts`, `useUIStore.ts`.
