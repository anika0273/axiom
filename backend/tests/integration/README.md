# tests/integration

Tests that hit a real (test) database and exercise full API routes.

Setup:
- Uses a separate `TEST_DATABASE_URL` pointing at a disposable Postgres instance
- Fixtures in `conftest.py` handle DB creation, schema application, and teardown
- FastAPI `TestClient` (sync) or `AsyncClient` from httpx for async routes

File naming: `test_<resource>_api.py` for endpoint tests, `test_<service>_db.py`
for service + DB integration.
Run with: `pytest tests/integration/`
