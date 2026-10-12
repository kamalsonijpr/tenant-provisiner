# Prompt 08: Tests For State And API

Continue from the existing project. Read `Control_Plane_CANDIDATE_BRIEF.md` and
`architecture.md` before editing.

Deepen the automated test suite for shared state rules and control-plane API behavior.

Create or update these files:

- `tests/`
- Any test fixtures needed under `tests/conftest.py`

Requirements:

- Add meaningful tests for:
  - slug validation
  - permanent slug uniqueness, including destroyed tenants
  - create lifecycle initial state
  - update allowed only from `active`
  - delete allowed only from `active` or `failed`
  - structured error codes
  - tenant version increments on API mutations
  - task creation as side effect of tenant mutations
  - complete outbox event payload creation as side effect of tenant mutations
  - task read-only HTTP behavior
- Keep tests deterministic.
- Prefer fixture helpers over copy-pasted setup.

Verification:

- Run the full pytest suite.
- Run ruff format/check.
- Report files changed and command results.

Do not change runtime behavior except to fix bugs revealed by these tests.
