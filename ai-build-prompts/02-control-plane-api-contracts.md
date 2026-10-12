# Prompt 02: Control Plane API Contracts

Continue from the existing project. Read `Control_Plane_CANDIDATE_BRIEF.md` and
`architecture.md` before editing.

Implement control-plane API schemas and structured error handling.

Create or update these files:

- `app/control_plane/api/errors.py`
- `app/control_plane/api/schemas.py`
- `app/control_plane/api/main.py`
- `tests/test_errors.py`

Requirements:

- Define Pydantic request/response schemas for tenants, tasks, pagination, and errors.
- Validate tenant slugs with `^[a-z][-a-z0-9]{1,26}[a-z0-9]$`.
- Validate tenant names as non-empty strings.
- Define structured error responses with this shape:
  `{"error":{"code":"...","message":"...","details":{...}}}`.
- Implement exceptions and handlers for:
  - `tenant_not_found`
  - `tenant_already_exists`
  - `tenant_update_not_allowed`
  - `tenant_version_conflict`
  - `task_not_found`
- Map required errors to documented HTTP statuses.
- Keep route handlers thin; business behavior will live in `app/control_plane/application`.

Verification:

- Run ruff format/check.
- Run pytest for schema and error tests.
- Report files changed and command results.

Do not implement full tenant/task endpoints yet.
