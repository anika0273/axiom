# services

Business logic layer. Services sit between the API routes and the database.

Rules:
- Each service is a plain async function or a class with injected `AsyncSession`
- No `Request`/`Response` objects — services are framework-agnostic
- Services may call other services but must not import from `api/`
- Stats and ML logic is delegated to `stats/` and `ml/` packages respectively
- AI summarisation is delegated to `ai/`

Expected files: `experiment_service.py`, `variant_service.py`,
`metric_service.py`, `assignment_service.py`, `report_service.py`
