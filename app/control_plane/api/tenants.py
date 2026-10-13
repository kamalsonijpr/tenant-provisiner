from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from app.control_plane.api.schemas import (
    PaginatedResponse,
    TenantCreate,
    TenantDelete,
    TenantResponse,
    TenantUpdate,
)
from app.control_plane.application import tenants
from app.shared.db import get_session
from app.shared.state import TenantStatus

router = APIRouter(prefix="/tenants", tags=["tenants"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant_endpoint(payload: TenantCreate, session: SessionDependency) -> TenantResponse:
    tenant = tenants.create_tenant(session, slug=payload.slug, name=payload.name)
    return TenantResponse.model_validate(tenant)


@router.get("", response_model=PaginatedResponse[TenantResponse])
def list_tenants_endpoint(
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(pattern=r"^\d+$")] = None,
    tenant_status: Annotated[TenantStatus | None, Query(alias="status")] = None,
) -> PaginatedResponse[TenantResponse]:
    page = tenants.list_tenants(session, limit=limit, cursor=cursor, status=tenant_status)
    return PaginatedResponse[TenantResponse](
        items=[TenantResponse.model_validate(tenant) for tenant in page.items],
        next_cursor=page.next_cursor,
    )


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant_endpoint(tenant_id: UUID, session: SessionDependency) -> TenantResponse:
    tenant = tenants.get_tenant(session, tenant_id)
    return TenantResponse.model_validate(tenant)


@router.patch("/{tenant_id}", response_model=TenantResponse)
def update_tenant_endpoint(
    tenant_id: UUID,
    payload: TenantUpdate,
    session: SessionDependency,
) -> TenantResponse:
    tenant = tenants.update_tenant(
        session,
        tenant_id=tenant_id,
        name=payload.name,
        version=payload.version,
    )
    return TenantResponse.model_validate(tenant)


@router.delete(
    "/{tenant_id}",
    response_model=TenantResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def delete_tenant_endpoint(
    tenant_id: UUID,
    session: SessionDependency,
    payload: Annotated[TenantDelete, Body()],
) -> TenantResponse:
    tenant = tenants.delete_tenant(session, tenant_id=tenant_id, version=payload.version)
    return TenantResponse.model_validate(tenant)
