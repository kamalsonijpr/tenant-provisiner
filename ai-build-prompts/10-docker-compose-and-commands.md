# Prompt 10: Docker Compose And Commands

Continue from the existing project. Read `Control_Plane_CANDIDATE_BRIEF.md` and
`architecture.md` before editing.

Implement the local runtime and one-command quality gates.

Create or update these files:

- `Dockerfile`
- `docker-compose.yml`
- `Makefile`
- `.env.example`
- Any entrypoint scripts needed under `scripts/`

Requirements:

- `make up` must be the single cold-start boot command.
- `make up` must build and start:
  - control-plane API
  - control-plane progress consumer
  - standalone outbox publisher
  - worker simulator
  - PostgreSQL
  - RabbitMQ
- `make test` must run the full automated test suite.
- `make lint` must run static analysis.
- `make format` must format code.
- `make security` must run bandit or the chosen security scanner.
- Compose services must use local development credentials only.
- Do not commit secrets.
- Ensure database migrations run before app processes handle traffic.
- Expose the API on a predictable local port.
- Expose RabbitMQ management UI for debugging.
- Use explicit module entrypoints that match the component layout, for example:
  - `app.control_plane.api.main`
  - `app.control_plane.consumers.worker_progress`
  - `app.outbox_publisher.publisher`
  - `app.worker.simulator`

Verification:

- Run `make lint`.
- Run `make test`.
- Boot with `make up` if possible and verify `GET /health`.
- Report files changed and command results.
