# Prompt 07: Worker Simulator

Continue from the existing project. Read `Control_Plane_CANDIDATE_BRIEF.md` and
`architecture.md` before editing.

Implement the standalone worker simulator component.

Create or update these files:

- `app/worker/__init__.py`
- `app/worker/simulator.py`
- `app/shared/broker.py`
- `tests/test_worker.py`

Requirements:

- Consume `task.created` messages.
- Emit `task.progress` messages for:
  - `in_progress`
  - then `done` or `failed`
- Support startup config via CLI args and/or environment variables:
  - `--fail-rate`
  - `--min-delay-ms`
  - `--max-delay-ms`
  - `--worker-id`
- Generate stable progress ids per task and status so retries do not create new
  idempotency keys for the same logical update.
- Acknowledge task messages only after progress messages are published.
- Validate incoming task-created payloads and handle poison messages safely.
- Do not import control-plane API, application services, or repositories from the worker.

Verification:

- Add tests for progress payload shape, stable ids, failure selection, and delay config.
- Run ruff format/check.
- Run pytest for worker tests.
- Report files changed and command results.
