from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.control_plane.api.main import create_app
from app.shared.db import Base, get_session
from app.shared.models import Task, Tenant
from app.shared.state import TaskStatus, TaskType, TenantStatus


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


def seed_task(
    database: sessionmaker[Session],
    *,
    tenant_id: UUID,
    task_type: TaskType,
    status: TaskStatus,
) -> Task:
    with database.begin() as session:
        task = Task(
            id=uuid4(),
            tenant_id=tenant_id,
            type=task_type,
            status=status,
        )
        session.add(task)
        session.flush()
        session.expunge(task)
        return task


@pytest.mark.asyncio
async def test_list_tasks_with_pagination_and_filters(
    client: AsyncClient,
    database: sessionmaker[Session],
) -> None:
    tenant_one = seed_tenant(database, slug="tenant-one")
    tenant_two = seed_tenant(database, slug="tenant-two")
    seed_task(
        database, tenant_id=tenant_one.id, task_type=TaskType.DEPLOY, status=TaskStatus.ACCEPTED
    )
    seed_task(
        database, tenant_id=tenant_one.id, task_type=TaskType.UPDATE, status=TaskStatus.IN_PROGRESS
    )
    seed_task(database, tenant_id=tenant_two.id, task_type=TaskType.DESTROY, status=TaskStatus.DONE)

    page = await client.get("/tasks", params={"limit": 1})
    filtered = await client.get(
        "/tasks",
        params={
            "tenant_id": tenant_one.id,
            "status": TaskStatus.ACCEPTED,
            "type": TaskType.DEPLOY,
        },
    )

    assert page.status_code == 200
    assert page.json()["items"][0]["tenant_id"]
    assert page.json()["next_cursor"] == "1"
    assert filtered.status_code == 200
    assert len(filtered.json()["items"]) == 1
    assert filtered.json()["items"][0]["type"] == TaskType.DEPLOY
    assert filtered.json()["items"][0]["status"] == TaskStatus.ACCEPTED


@pytest.mark.asyncio
async def test_get_task_returns_task_and_missing_task_returns_not_found(
    client: AsyncClient,
    database: sessionmaker[Session],
) -> None:
    tenant = seed_tenant(database, slug="task-tenant")
    task = seed_task(
        database, tenant_id=tenant.id, task_type=TaskType.DEPLOY, status=TaskStatus.ACCEPTED
    )

    response = await client.get(f"/tasks/{task.id}")
    missing = await client.get(f"/tasks/{uuid4()}")

    assert response.status_code == 200
    assert response.json()["id"] == str(task.id)
    assert response.json()["type"] == TaskType.DEPLOY
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "task_not_found"
