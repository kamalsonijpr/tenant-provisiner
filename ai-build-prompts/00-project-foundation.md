# Prompt 00: Project Foundation

You are building the Tenant Provisioning Control Plane described in
`Control_Plane_CANDIDATE_BRIEF.md` and `architecture.md`.

Implement the initial Python project foundation only, using the component-oriented
layout from `architecture.md`.

Create or update these files:

- `pyproject.toml`
- `app/__init__.py`
- `app/control_plane/__init__.py`
- `app/control_plane/api/__init__.py`
- `app/control_plane/api/main.py`
- `app/shared/__init__.py`
- `app/shared/config.py`
- `app/shared/time.py`
- `tests/__init__.py`
- `tests/test_health.py`

Requirements:

- Use Python 3.12.
- Use FastAPI.
- Add a health endpoint: `GET /health` returns `{"status":"ok"}`.
- Add typed settings in `app/shared/config.py` using environment variables.
- Add a UTC timestamp helper that formats API timestamps as ISO 8601 with milliseconds and `Z`.
- Configure ruff, pytest, pytest-asyncio, httpx, mypy-compatible typing, and bandit in `pyproject.toml`.
- Keep dependencies minimal and appropriate for the planned stack.

Verification:

- Run formatter/linter if available.
- Run `pytest`.
- Report files changed and command results.

Do not implement domain models, database access, Docker, or messaging in this step.
