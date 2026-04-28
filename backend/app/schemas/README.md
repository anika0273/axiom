# schemas

Pydantic v2 request/response models. No SQLAlchemy here.

Convention:
- `ExperimentCreate` — fields accepted on POST
- `ExperimentUpdate` — fields accepted on PATCH (all optional)
- `ExperimentRead` — fields returned to clients (includes `id`, timestamps)
- `ExperimentList` — paginated list wrapper

Use `model_config = ConfigDict(from_attributes=True)` on read schemas so they
can be constructed from ORM objects via `model_validate(orm_obj)`.
