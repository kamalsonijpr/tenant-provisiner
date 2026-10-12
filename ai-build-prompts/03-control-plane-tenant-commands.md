# Prompt 03: Control Plane Tenant Commands

Continue from the existing project. Read `Control_Plane_CANDIDATE_BRIEF.md` and
`architecture.md` before editing.

Implement tenant CRUD endpoints and control-plane command behavior.

Create or update these files:

- `app/control_plane/api/tenants.py`
- `app/control_plane/api/main.py`
- `app/control_plane/application/tenants.py`
- `app/control_plane/repositories/tenants.py`
- `app/control_plane/repositories/tasks.py`
- `app/control_plane/repositories/outbox.py`
- `tests/test_tenants_api.py`

Requirements:

- Implement:
  - `POST /tenants`
  - `GET /tenants`
  - `GET /tenants/{tenant_id}`
  - `PATCH /tenants/{tenant_id}`
  - `DELETE /tenants/{tenant_id}`
- Creating a tenant must create a `provisioning` tenant, a `deploy` task with
  `accepted` status, and a complete outbox event payload in one transaction.
- Updating a tenant must be allowed only from `active`, require matching `version`, move
  tenant to `updating`, increment version, create an `update` task, and create a
  complete outbox event payload in one transaction.
- Deleting a tenant must be allowed only from `active` or `failed`, require matching
  `version`, move tenant to `destroying`, increment version, create a `destroy` task,
  and create a complete outbox event payload in one transaction.
- Permanent slug uniqueness must return `tenant_already_exists`.
- Use database-level optimistic locking, not only in-memory checks.
- Implement simple cursor or offset pagination consistently.
- The control plane owns event creation; the future outbox publisher must only deliver
  stored outbox payloads.

Verification:

- Add API tests for create/list/get/update/delete and required structured errors.
- Run ruff format/check.
- Run pytest for tenant API tests.
- Report files changed and command results.

Do not implement RabbitMQ publishing yet; only persist outbox events.
