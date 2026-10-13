from __future__ import annotations

from uuid import uuid4

import pytest

from app.worker.simulator import (
    build_progress_payload,
    build_progress_updates,
    parse_task_created_payload,
    resolve_delay_ms,
    should_fail_task,
)


def test_worker_progress_payload_has_expected_shape() -> None:
    task_id = str(uuid4())
    payload = build_progress_payload(task_id, "in_progress", worker_id="worker-1")

    assert payload["task_id"] == task_id
    assert payload["status"] == "in_progress"
    assert payload["worker_id"] == "worker-1"
    assert payload["id"]
    assert payload["occurred_at"].endswith("Z")


def test_worker_progress_ids_are_stable_across_retries() -> None:
    task_id = str(uuid4())

    first = build_progress_payload(task_id, "done", worker_id="worker-1")
    second = build_progress_payload(task_id, "done", worker_id="worker-1")

    assert first["id"] == second["id"]


def test_worker_uses_deterministic_failure_selection() -> None:
    task_id = str(uuid4())

    assert should_fail_task(task_id, fail_rate=0.0, worker_id="worker-1") is False
    assert should_fail_task(task_id, fail_rate=1.0, worker_id="worker-1") is True
    assert should_fail_task(task_id, fail_rate=0.5, worker_id="worker-1") in {True, False}


def test_worker_builds_in_progress_then_terminal_progress() -> None:
    task_id = str(uuid4())
    updates = build_progress_updates(
        task_id,
        fail_rate=0.0,
        min_delay_ms=10,
        max_delay_ms=30,
        worker_id="worker-1",
    )

    assert [item["status"] for item in updates] == ["in_progress", "done"]
    assert updates[0]["id"] != updates[1]["id"]
    assert updates[0]["task_id"] == task_id
    assert updates[1]["task_id"] == task_id


def test_worker_delay_config_is_within_expected_range() -> None:
    task_id = str(uuid4())
    delay = resolve_delay_ms(task_id, min_delay_ms=25, max_delay_ms=75, worker_id="worker-1")

    assert 25 <= delay <= 75


def test_worker_rejects_invalid_task_created_payload() -> None:
    with pytest.raises(ValueError):
        parse_task_created_payload({"event_type": "task.updated"})
