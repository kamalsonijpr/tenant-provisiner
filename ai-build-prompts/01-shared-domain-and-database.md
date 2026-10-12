# Prompt 01: Shared Domain And Database

Continue from the existing project. Read `Control_Plane_CANDIDATE_BRIEF.md` and
`architecture.md` before editing.

Implement shared domain contracts and the database foundation.

Create or update these files:

- `app/shared/db.py`
- `app/shared/models.py`
- `app/shared/state.py`
- `app/control_plane/application/__init__.py`
- `app/control_plane/repositories/__init__.py`
- `migrations/`
- `tests/test_shared_state.py`

Requirements:

- Use SQLAlchemy 2.x typed models.
- Model tenants, tasks, outbox events, and processed worker updates.
- Use UUID primary keys.
- Enforce permanent unique `tenant.slug`.
- Enforce valid enum values for tenant status, task type, and task status.
- Add database indexes needed for list endpoints, processed worker update lookup, and outbox polling.
- Add Alembic migration setup and an initial migration.
- Implement pure state transition helpers in `app/shared/state.py`.
- Keep `app/shared/state.py` independent of FastAPI, RabbitMQ, SQLAlchemy sessions, and repositories.
- Unit test allowed and rejected state transitions.

Verification:

- Run ruff format/check.
- Run pytest for shared state tests.
- Report files changed and command results.

Do not implement HTTP endpoints beyond health and do not implement RabbitMQ yet.
