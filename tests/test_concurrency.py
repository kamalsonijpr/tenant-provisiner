from __future__ import annotations

import os
import tempfile
import threading
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.control_plane.application import tenants as tenant_service
from app.control_plane.repositories import tenants as tenant_repository
from app.shared.db import Base
from app.shared.state import TenantStatus


@pytest.fixture
def database() -> Generator[sessionmaker[Session], None, None]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield session_factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
        os.remove(path)


def test_two_simultaneous_patch_requests_with_same_version_only_one_succeeds(
    database: sessionmaker[Session],
) -> None:
    with database.begin() as session:
        tenant = tenant_repository.add_tenant(
            session,
            slug="race-patch",
            name="Race Patch",
            status=TenantStatus.ACTIVE,
        )

    tenant_id = tenant.id
    barrier = threading.Barrier(2)
    results: list[tuple[str, str]] = []

    def worker(name: str) -> None:
        barrier.wait()
        try:
            with database() as session:
                tenant_service.update_tenant(
                    session,
                    tenant_id=tenant_id,
                    name=name,
                    version=1,
                )
            results.append(("success", name))
        except Exception as exc:  # pragma: no cover - exercised by the race condition
            results.append(("error", type(exc).__name__))

    threads = [
        threading.Thread(target=worker, args=("Updated One",)),
        threading.Thread(target=worker, args=("Updated Two",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(result[0] == "success" for result in results) == 1
    assert sum(result[0] == "error" for result in results) == 1


def test_two_simultaneous_create_requests_with_same_slug_only_one_succeeds(
    database: sessionmaker[Session],
) -> None:
    barrier = threading.Barrier(2)
    results: list[tuple[str, str]] = []

    def worker(name: str) -> None:
        barrier.wait()
        try:
            with database() as session:
                tenant_service.create_tenant(session, slug="race-create", name=name)
            results.append(("success", name))
        except Exception as exc:  # pragma: no cover - exercised by the race condition
            results.append(("error", type(exc).__name__))

    threads = [
        threading.Thread(target=worker, args=("Create One",)),
        threading.Thread(target=worker, args=("Create Two",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(result[0] == "success" for result in results) == 1
    assert sum(result[0] == "error" for result in results) == 1
