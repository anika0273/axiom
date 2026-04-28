# models

SQLAlchemy ORM table definitions. One file per domain entity.

Rules:
- All models extend `Base` from `app/db/base.py`
- Column types are fully typed with SQLAlchemy 2.x `Mapped[...]` annotations
- No Pydantic here — that belongs in `schemas/`
- Relationships are declared with `relationship()` and `back_populates`
- Table names are lowercase snake_case

Expected files: `experiment.py`, `variant.py`, `metric.py`, `user.py`, `event.py`
