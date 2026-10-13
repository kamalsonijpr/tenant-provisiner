# Tenant Provisioning Control Plane

A local, containerized Python implementation of the tenant provisioning control plane described in the brief. It contains four runtime components: `control_plane`, `outbox_publisher`, `worker`, and `shared`.

## Architecture

```mermaid
flowchart LR
    Client[API Client] --> API[control_plane API]
    API --> DB[(PostgreSQL)]
    API --> Outbox[(outbox_events)]
    OutboxPublisher[outbox_publisher] --> DB
    OutboxPublisher --> TaskQueue[(RabbitMQ task.created)]
    TaskQueue --> Worker[worker simulator]
    Worker --> ProgressQueue[(RabbitMQ task.progress)]
    ProgressQueue --> ProgressConsumer[control_plane progress consumer]
    ProgressConsumer --> DB
```

- `app/control_plane`: HTTP API, task queries, and worker-progress ingestion.
- `app/outbox_publisher`: publishes committed outbox rows to RabbitMQ.
- `app/worker`: simulates provisioning and emits `in_progress` / terminal status updates.
- `app/shared`: database, broker helpers, config, and shared state definitions.

## Design decisions and trade-offs

- PostgreSQL is the source of truth for tenants, tasks, and outbox events to preserve transactional ordering and optimistic locking.
- RabbitMQ is used as the durable handoff between control plane and worker; the design assumes at-least-once delivery and makes handlers idempotent.
- The outbox pattern ensures task events are published only after a database transaction commits, avoiding the classic "publish-before-commit" bug.
- Worker simulations are intentionally lightweight; they consume task.created messages and emit deterministic progress updates with stable idempotency keys.

## Local setup

Copy the example environment file if you want to override local defaults:

```bash
cp .env.example .env
```

Then start the full stack:

```bash
make up
```

This builds the Docker image and boots:

- API on `http://localhost:8000`
- RabbitMQ management UI on `http://localhost:15672`
- PostgreSQL on `localhost:5432`
- Control-plane progress consumer
- Outbox publisher
- Worker simulator

The API health check is available at:

```bash
curl http://localhost:8000/health
```

## Quality gates

```bash
make test
make lint
make format
make security
```

## API examples

Create a tenant:

```bash
curl -sS -X POST http://localhost:8000/tenants   -H 'Content-Type: application/json'   -d '{"slug":"acme","name":"Acme Labs"}'
```

List tenants:

```bash
curl -sS 'http://localhost:8000/tenants?limit=20'
```

Fetch a tenant detail:

```bash
curl -sS http://localhost:8000/tenants/<tenant-id>
```

Update a tenant (requires the current version):

```bash
curl -sS -X PATCH http://localhost:8000/tenants/<tenant-id>   -H 'Content-Type: application/json'   -d '{"name":"Acme Labs Updated","version":1}'
```

Delete a tenant:

```bash
curl -sS -X DELETE http://localhost:8000/tenants/<tenant-id>   -H 'Content-Type: application/json'   -d '{"version":2}'
```

List tasks:

```bash
curl -sS 'http://localhost:8000/tasks?limit=20'
```

## Task lifecycle observation

The worker consumes task-created events and advances each task from `accepted` to `in_progress` to `done` or `failed`.

```bash
curl -sS http://localhost:8000/tasks
curl -sS http://localhost:8000/tenants/<tenant-id>
```

The tenant status will move as follows:

- create: `provisioning`
- worker deploy completes: `active`
- update: `updating -> active`
- delete: `destroying -> destroyed`
- worker failure: `failed`

## Failure and negative-scenario demos

Force a failed worker simulation without changing the code:

```bash
docker compose run --rm worker python -m app.worker.simulator --fail-rate 1.0 --min-delay-ms 250 --max-delay-ms 750
```

That creates a terminal failed task and moves the tenant to `failed` when the progress consumer applies it.

## Duplicate and stale progress events

Publish a manual progress event directly to RabbitMQ for redelivery or out-of-order testing:

```bash
python scripts/publish_progress.py   --task-id <task-uuid>   --status in_progress   --worker-id demo-worker   --idempotency-key stale-progress   --rabbitmq-url amqp://guest:guest@localhost:5672/
```

The consumer ignores duplicate or stale updates based on the task state and the idempotency key.

## Concurrency demo

This script fires two PATCH requests at the same version to confirm only one can succeed:

```bash
python scripts/concurrency_check.py   --base-url http://localhost:8000   --slug race-demo   --name "Race Demo"   --version 1
```

## No secrets

Use local development credentials only; do not commit real secrets. The tracked example files use local values for the Docker stack and are safe for the repo.
