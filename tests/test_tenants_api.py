from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.control_plane.api.main import create_app
from app.shared.db import Base, get_session
from app.shared.models import OutboxEvent, Task, Tenant
from app.shared.state import TaskStatus, TaskType, TenantStatus
from app.shared.time import format_utc_millis


@pytest.fixture
def database() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield testing_session
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest_asyncio.fixture
async def client(database: sessionmaker[Session]) -> Generator[AsyncClient, None, None]:
    app = create_app()

    def override_get_session() -> Generator[Session, None, None]:
        with database() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def seed_tenant(
    database: sessionmaker[Session],
    *,
    status: TenantStatus = TenantStatus.ACTIVE,
    slug: str | None = None,
    version: int = 1,
) -> Tenant:
    with database.begin() as session:
        tenant = Tenant(
            slug=slug or f"tenant-{uuid4().hex[:8]}",
            name="Seed Tenant",
            status=status,
            version=version,
        )
        session.add(tenant)
        session.flush()
        session.expunge(tenant)
        return tenant


@pytest.mark.asyncio
async def test_create_tenant_persists_tenant_task_and_complete_outbox_event(
    client: AsyncClient,
    database: sessionmaker[Session],
) -> None:
    response = await client.post("/tenants", json={"slug": "new-tenant", "name": "New"})

    assert response.status_code == 201
    tenant = response.json()
    assert tenant["slug"] == "new-tenant"
    assert tenant["status"] == TenantStatus.PROVISIONING
    assert tenant["version"] == 1
    assert tenant["created_at"].endswith("Z")

    with database() as session:
        task = session.scalar(select(Task).where(Task.tenant_id == UUID(tenant["id"])))
        event = session.scalar(select(OutboxEvent))
    assert task is not None
    assert task.type is TaskType.DEPLOY
    assert task.status is TaskStatus.ACCEPTED
    assert event is not None
    assert event.id == task.id
    assert event.event_type == "task.created"
    assert event.exchange == "tenant-provisioning"
    assert event.routing_key == "task.created"
    assert event.payload["task"] == {
        "id": str(task.id),
        "type": "deploy",
        "tenant_id": tenant["id"],
        "status": "accepted",
        "created_at": format_utc_millis(task.created_at),
        "updated_at": format_utc_millis(task.updated_at),
    }


@pytest.mark.asyncio
async def test_slug_is_permanently_unique(client: AsyncClient) -> None:
    payload = {"slug": "reused-slug", "name": "Tenant"}
    assert (await client.post("/tenants", json=payload)).status_code == 201

    response = await client.post("/tenants", json=payload)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "tenant_already_exists"


@pytest.mark.asyncio
async def test_list_and_get_tenants_with_offset_pagination(
    client: AsyncClient,
    database: sessionmaker[Session],
) -> None:
    first = seed_tenant(database, slug="first-tenant")
    second = seed_tenant(database, slug="second-tenant")

    first_page = await client.get("/tenants", params={"limit": 1})
    second_page = await client.get(
        "/tenants",
        params={"limit": 1, "cursor": first_page.json()["next_cursor"]},
    )
    fetched = await client.get(f"/tenants/{first.id}")

    assert first_page.status_code == 200
    assert first_page.json()["items"][0]["id"] == str(first.id)
    assert first_page.json()["next_cursor"] == "1"
    assert second_page.json()["items"][0]["id"] == str(second.id)
    assert second_page.json()["next_cursor"] is None
    assert fetched.status_code == 200
    assert fetched.json()["id"] == str(first.id)


@pytest.mark.asyncio
async def test_get_missing_tenant_returns_structured_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/tenants/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "tenant_not_found"


@pytest.mark.asyncio
async def test_update_tenant_requires_active_and_matching_version(
    client: AsyncClient,
    database: sessionmaker[Session],
) -> None:
    tenant = seed_tenant(database, slug="update-tenant")
    updated = await client.patch(
        f"/tenants/{tenant.id}",
        json={"name": "Updated", "version": 1},
    )

    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated"
    assert updated.json()["status"] == "updating"
    assert updated.json()["version"] == 2

    conflict = await client.patch(
        f"/tenants/{tenant.id}",
        json={"name": "Stale", "version": 1},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "tenant_version_conflict"
    assert conflict.json()["error"]["details"] == {
        "expected_version": 1,
        "actual_version": 2,
    }

    with database() as session:
        task = session.scalar(select(Task).where(Task.tenant_id == tenant.id))
        events = list(session.scalars(select(OutboxEvent)))
    assert task is not None and task.type is TaskType.UPDATE
    assert len(events) == 1


@pytest.mark.asyncio
async def test_update_not_allowed_for_non_active_tenant(
    client: AsyncClient,
    database: sessionmaker[Session],
) -> None:
    tenant = seed_tenant(database, status=TenantStatus.PROVISIONING)
    response = await client.patch(
        f"/tenants/{tenant.id}",
        json={"name": "Updated", "version": 1},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "tenant_update_not_allowed"


@pytest.mark.asyncio
async def test_delete_active_tenant_creates_destroy_task_and_outbox(
    client: AsyncClient,
    database: sessionmaker[Session],
) -> None:
    tenant = seed_tenant(database, slug="delete-tenant")
    response = await client.request(
        "DELETE",
        f"/tenants/{tenant.id}",
        json={"version": 1},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "destroying"
    assert response.json()["version"] == 2
    with database() as session:
        task = session.scalar(select(Task).where(Task.tenant_id == tenant.id))
        event = session.scalar(select(OutboxEvent))
    assert task is not None and task.type is TaskType.DESTROY
    assert event is not None and event.payload["task"]["id"] == str(task.id)


@pytest.mark.asyncio
async def test_delete_failed_tenant_is_allowed_and_other_states_are_rejected(
    client: AsyncClient,
    database: sessionmaker[Session],
) -> None:
    failed = seed_tenant(database, status=TenantStatus.FAILED, slug="failed-tenant")
    accepted = await client.request(
        "DELETE",
        f"/tenants/{failed.id}",
        json={"version": 1},
    )
    assert accepted.status_code == 202

    provisioning = seed_tenant(database, status=TenantStatus.PROVISIONING)
    rejected = await client.request(
        "DELETE",
        f"/tenants/{provisioning.id}",
        json={"version": 1},
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "tenant_update_not_allowed"


@pytest.mark.asyncio
async def test_delete_checks_version_before_status(
    client: AsyncClient,
    database: sessionmaker[Session],
) -> None:
    tenant = seed_tenant(database, status=TenantStatus.PROVISIONING, version=2)
    response = await client.request(
        "DELETE",
        f"/tenants/{tenant.id}",
        json={"version": 1},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "tenant_version_conflict"
