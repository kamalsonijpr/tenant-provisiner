# Build Plan

Use the prompt files in `ai-build-prompts/` in numeric order. Feed exactly one prompt at
a time to the coding agent, review the diff and tests after each step, then continue.

The prompts build the app by component:

- `control_plane`: HTTP API, tenant/task application logic, repositories, and the worker-progress consumer.
- `outbox_publisher`: separate delivery service for committed outbox rows.
- `worker`: simulator that consumes task-created events and publishes progress.
- `shared`: cross-component contracts and infrastructure helpers.

## Prompt Sequence

1. `ai-build-prompts/00-project-foundation.md`
2. `ai-build-prompts/01-shared-domain-and-database.md`
3. `ai-build-prompts/02-control-plane-api-contracts.md`
4. `ai-build-prompts/03-control-plane-tenant-commands.md`
5. `ai-build-prompts/04-control-plane-task-queries.md`
6. `ai-build-prompts/05-outbox-publisher.md`
7. `ai-build-prompts/06-control-plane-progress-consumer.md`
8. `ai-build-prompts/07-worker-simulator.md`
9. `ai-build-prompts/08-tests-state-and-api.md`
10. `ai-build-prompts/09-tests-messaging-and-concurrency.md`
11. `ai-build-prompts/10-docker-compose-and-commands.md`
12. `ai-build-prompts/11-readme-and-final-polish.md`

## Review Gate After Every Prompt

After each prompt, require the agent to report:

- Files changed.
- Tests added or updated.
- Exact command output for the relevant quality gate.
- Any intentional trade-off or deferred item.

Do not proceed to the next prompt until the current step runs locally or the failure is
understood and written down.

## Non-Negotiables

- Do not publish RabbitMQ events directly from request handlers.
- Do not let the outbox publisher construct domain events from tenant/task state; the
  control plane writes the full event payload into the outbox.
- Do not use in-memory state for tenants, tasks, idempotency, or outbox events.
- Do not treat worker progress messages as exactly-once.
- Do not implement tenant version checks only in application memory.
- Do not let the worker import control-plane API or repository code.
- Do not add secrets or environment-specific credentials to the repository.
