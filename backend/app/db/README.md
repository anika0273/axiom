# db

Database engine, session management, and migrations.

| File/Folder | Purpose |
|---|---|
| `engine.py` | Async SQLAlchemy engine and `AsyncSessionLocal` factory |
| `deps.py` | FastAPI dependency that yields a scoped `AsyncSession` |
| `base.py` | Declarative `Base` imported by all ORM models |
| `alembic/` | Alembic migration environment and version scripts |

All models must import `Base` from `db/base.py`. Migrations are generated with:
```
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```
