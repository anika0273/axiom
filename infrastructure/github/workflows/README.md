# infrastructure/github/workflows

GitHub Actions CI/CD pipelines.

Planned workflows:
- `ci.yml` — On every PR: run `pytest`, `ruff`, `black --check`, TypeScript `tsc --noEmit`
- `deploy-staging.yml` — On merge to `main`: build Docker images, push to registry, deploy to Railway staging
- `deploy-prod.yml` — On version tag (`v*`): deploy to Railway production

Secrets (`ANTHROPIC_API_KEY`, `RAILWAY_TOKEN`, `DATABASE_URL`) are stored in
GitHub repo secrets and injected as environment variables.
