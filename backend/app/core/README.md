# core

Application-wide infrastructure — loaded once at startup.

| File | Purpose |
|---|---|
| `config.py` | `pydantic-settings` Settings class; all env vars read here |
| `security.py` | JWT creation/verification, password hashing |
| `logging.py` | Structured logging setup (JSON in production) |
| `lifespan.py` | FastAPI lifespan handler — DB pool init/teardown |

No business logic lives here. No imports from `services/` or `api/`.
