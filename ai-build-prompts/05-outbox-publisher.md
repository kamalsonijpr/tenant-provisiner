# Prompt 05: Outbox Publisher

Continue from the existing project. Read `Control_Plane_CANDIDATE_BRIEF.md` and
`architecture.md` before editing.

Implement shared RabbitMQ setup and the standalone outbox publisher component.

Create or update these files:

- `app/shared/broker.py`
- `app/shared/config.py`
- `app/outbox_publisher/__init__.py`
- `app/outbox_publisher/publisher.py`
- `app/outbox_publisher/repository.py`
- `tests/test_outbox_publisher.py`

Requirements:

- Use aio-pika.
- Declare exchange `tenant-provisioning`.
- Declare queue/routing key `task.created`.
- Implement an outbox publisher process that:
  - Reads unpublished outbox rows.
  - Publishes the stored JSON payload to the row's exchange/routing key.
  - Marks rows as published only after broker publish succeeds.
  - Retries transient broker failures with backoff.
  - Does not crash permanently on one bad row.
- The publisher must not construct task events from tenants or tasks.
- The publisher must not import control-plane API, application services, or repositories.
- Use `app/outbox_publisher/repository.py` for selecting unpublished rows and marking
  published rows. It should operate on the shared outbox model.
- Make publisher batch size and poll interval configurable.

Verification:

- Add unit tests for selecting rows, publishing stored payloads, and marking rows published.
- If integration broker tests are not yet practical, clearly mark what remains for the
  Docker Compose step.
- Run ruff format/check.
- Run pytest for outbox publisher tests.
- Report files changed and command results.
