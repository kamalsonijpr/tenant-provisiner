# Prompt 09: Tests For Messaging And Concurrency

Continue from the existing project. Read `Control_Plane_CANDIDATE_BRIEF.md` and
`architecture.md` before editing.

Add tests and scripts that prove concurrency and messaging correctness.

Create or update these files:

- `tests/test_concurrency.py`
- `tests/test_messaging_integration.py`
- `scripts/concurrency_check.py`
- `scripts/publish_progress.py`

Requirements:

- Test two simultaneous PATCH requests with the same version and assert exactly one
  succeeds.
- Test two simultaneous creates with the same slug and assert exactly one succeeds.
- Test duplicate worker progress delivery changes state only once.
- Test out-of-order worker progress delivery does not regress a terminal task.
- Test the outbox publisher delivers the stored payload rather than reconstructing the event.
- Add a script that demonstrates concurrent PATCH behavior against a running API.
- Add a script that publishes manual progress messages to RabbitMQ for negative scenario
  demos.
- Scripts must be documented enough to be safely run from the README later.

Verification:

- Run the relevant concurrency and messaging tests.
- Run the full pytest suite if runtime is reasonable.
- Run ruff format/check.
- Report files changed and command results.
