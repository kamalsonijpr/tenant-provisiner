from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.control_plane.api.errors import (
    ApiError,
    TaskNotFoundError,
    TenantAlreadyExistsError,
    TenantNotFoundError,
    TenantUpdateNotAllowedError,
    TenantVersionConflictError,
    register_exception_handlers,
)
from app.control_plane.api.schemas import (
    ErrorResponse,
    PaginatedResponse,
    PaginationParams,
    TaskResponse,
    TenantCreate,
    TenantDelete,
    TenantResponse,
    TenantUpdate,
)
from app.shared.state import TaskStatus, TaskType, TenantStatus


@pytest.mark.parametrize(
    ("exception", "status_code", "code"),
    [
        (TenantNotFoundError(uuid4()), 404, "tenant_not_found"),
        (TenantAlreadyExistsError("acme"), 409, "tenant_already_exists"),
        (
            TenantUpdateNotAllowedError("provisioning", "updated"),
            409,
            "tenant_update_not_allowed",
        ),
        (TenantVersionConflictError(2, 3), 409, "tenant_version_conflict"),
        (TaskNotFoundError(uuid4()), 404, "task_not_found"),
    ],
)
@pytest.mark.asyncio
async def test_api_errors_use_structured_responses(
    exception: ApiError, status_code: int, code: str
) -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/error")
    async def raise_error() -> None:
        raise exception

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/error")

    assert response.status_code == status_code
    error = ErrorResponse.model_validate(response.json()).error
    assert error.code == code
    assert error.message
    assert isinstance(error.details, dict)


@pytest.mark.parametrize(
    "slug",
    ["ab", "Acd", "1abc", "abc-", "abc_", "a" * 29],
)
def test_tenant_create_rejects_invalid_slug(slug: str) -> None:
    with pytest.raises(ValidationError):
        TenantCreate(slug=slug, name="Tenant")


@pytest.mark.parametrize("slug", ["abc", "a-b", "a1b", "a" + "b" * 26 + "1"])
def test_tenant_create_accepts_valid_slug(slug: str) -> None:
    assert TenantCreate(slug=slug, name="Tenant").slug == slug


@pytest.mark.parametrize("name", ["", "x" * 256])
def test_tenant_create_rejects_invalid_name(name: str) -> None:
    with pytest.raises(ValidationError):
        TenantCreate(slug="valid-tenant", name=name)


def test_tenant_mutation_and_pagination_schemas_validate_constraints() -> None:
    assert TenantUpdate(name="Renamed", version=1).version == 1
    assert TenantDelete(version=2).version == 2
    assert PaginationParams().limit == 20
    assert PaginationParams(limit=100, cursor="next").cursor == "next"

    with pytest.raises(ValidationError):
        TenantUpdate(name="", version=1)
    with pytest.raises(ValidationError):
        TenantDelete(version=0)
    with pytest.raises(ValidationError):
        PaginationParams(limit=101)


def test_response_schemas_accept_domain_enums_and_paginated_items() -> None:
    tenant_id = uuid4()
    task_id = uuid4()
    tenant = TenantResponse(
        id=tenant_id,
        slug="valid-tenant",
        name="Tenant",
        status=TenantStatus.ACTIVE,
        version=1,
        created_at="2026-10-13T10:00:00Z",
        updated_at="2026-10-13T10:00:00Z",
    )
    task = TaskResponse(
        id=task_id,
        type=TaskType.DEPLOY,
        tenant_id=tenant_id,
        status=TaskStatus.ACCEPTED,
        created_at="2026-10-13T10:00:00Z",
        updated_at="2026-10-13T10:00:00Z",
    )

    assert tenant.model_dump(mode="json")["created_at"] == "2026-10-13T10:00:00.000Z"
    page = PaginatedResponse[TenantResponse](items=[tenant], next_cursor=None)
    assert page.items == [tenant]
    assert task.status is TaskStatus.ACCEPTED
