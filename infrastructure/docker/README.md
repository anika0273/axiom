# infrastructure/docker

Dockerfiles for each service.

| File | Purpose |
|---|---|
| `Dockerfile.backend` | Multi-stage Python image — builder installs deps, final is slim |
| `Dockerfile.frontend` | Multi-stage Node image — builder runs Vite build, final serves via nginx |

The root `docker-compose.yml` wires these together with the Postgres service
and mounts `.env` for local development.
