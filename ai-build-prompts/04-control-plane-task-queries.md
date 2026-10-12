# Prompt 04: Control Plane Task Queries

Continue from the existing project. Read `Control_Plane_CANDIDATE_BRIEF.md` and
`architecture.md` before editing.

Implement read-only task endpoints in the control plane.

Create or update these files:

- `app/control_plane/api/tasks.py`
- `app/control_plane/api/main.py`
- `app/control_plane/application/tasks.py`
- `app/control_plane/repositories/tasks.py`
- `tests/test_tasks_api.py`

Requirements:

- Implement:
  - `GET /tasks`
  - `GET /tasks/{task_id}`
- Support pagination.
- Support filters for `tenant_id`, `status`, and `type`.
- Return `task_not_found` for missing task details.
- Do not allow task creation or mutation over HTTP.
- Keep API routes thin by delegating query behavior to `app/control_plane/application/tasks.py`.

Verification:

- Add API tests for list, filters, get, and not-found errors.
- Run ruff format/check.
- Run pytest for task tests.
- Report files changed and command results.
