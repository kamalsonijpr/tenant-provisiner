# Prompt 06: Control Plane Progress Consumer

Continue from the existing project. Read `Control_Plane_CANDIDATE_BRIEF.md` and
`architecture.md` before editing.

Implement the control-plane consumer for inbound worker progress messages.

Create or update these files:

- `app/control_plane/application/progress.py`
- `app/control_plane/consumers/__init__.py`
- `app/control_plane/consumers/worker_progress.py`
- `app/control_plane/repositories/tasks.py`
- `app/control_plane/repositories/tenants.py`
- `app/control_plane/repositories/processed_worker_updates.py`
- `app/shared/broker.py`
- `tests/test_progress_consumer.py`

Requirements:

- Consume from queue/routing key `task.progress`.
- Progress payload must include:
  - stable `id` idempotency key
  - `task_id`
  - target task `status`
  - `occurred_at`
- Store processed worker update ids in the database.
- Apply task status transitions idempotently.
- Ignore duplicate messages.
- Ignore stale messages that would regress task state.
- Ignore updates for terminal tasks.
- On terminal task result, update the tenant status according to task type and outcome.
- Increment tenant version for every worker-applied terminal mutation.
- Use one database transaction for idempotency recording, task update, and tenant update.
- Retry transient broker failures with backoff.
- Poison messages must be acknowledged or routed aside without killing the consumer.
- This consumer belongs to the control plane because it interprets worker updates and
  mutates tenant/task state.

Verification:

- Add tests for duplicate progress, stale progress, terminal progress, and failed progress.
- Run ruff format/check.
- Run pytest for consumer tests.
- Report files changed and command results.
