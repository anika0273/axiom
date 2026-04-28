# api/v1/endpoints

One FastAPI `APIRouter` per resource, e.g. `experiments.py`, `metrics.py`, `users.py`.

Each file:
- Imports its router from `fastapi`
- Declares route handlers with full type annotations and docstrings
- Delegates all business logic to the corresponding service in `app/services/`
- Never touches the database directly — always via a service

Mount routers in `app/api/v1/router.py`, which is included in `app/main.py`.
