# tests/unit

Fast, in-memory tests for pure functions — no database, no network.

Coverage targets:
- 100% of `app/stats/` functions
- 100% of `app/ml/` public functions
- Key service logic that can be tested with mocked dependencies

File naming: `test_<module_name>.py` mirroring the source tree.
Run with: `pytest tests/unit/`
