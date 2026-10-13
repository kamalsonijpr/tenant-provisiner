from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.shared.models import Tenant
from app.shared.state import TenantStatus
from app.shared.time import utc_now


def add_tenant(
    session: Session,
    *,
    slug: str,
    name: str,
    status: TenantStatus,
) -> Tenant:
    tenant = Tenant(
        slug=slug,
        name=name,
        status=status,
        version=1,
    )
    session.add(tenant)
    session.flush()
    return tenant


def get_tenant(session: Session, tenant_id: UUID) -> Tenant | None:
    return session.get(Tenant, tenant_id)


def reload_tenant(session: Session, tenant_id: UUID) -> Tenant | None:
    return session.scalar(
        select(Tenant).where(Tenant.id == tenant_id).execution_options(populate_existing=True)
    )


def list_tenants(
    session: Session,
    *,
    offset: int,
    limit: int,
    status: TenantStatus | None,
) -> list[Tenant]:
    query = select(Tenant).order_by(Tenant.created_at, Tenant.id)
    if status is not None:
        query = query.where(Tenant.status == status)
    return list(session.scalars(query.offset(offset).limit(limit + 1)))


def update_tenant_if_version_matches(
    session: Session,
    *,
    tenant_id: UUID,
    version: int,
    name: str,
    current_status: TenantStatus,
    new_status: TenantStatus,
) -> bool:
    result = session.execute(
        update(Tenant)
        .where(
            Tenant.id == tenant_id,
            Tenant.version == version,
            Tenant.status == current_status,
        )
        .values(
            name=name,
            status=new_status,
            version=Tenant.version + 1,
            updated_at=utc_now(),
        )
        .returning(Tenant.id)
    )
    return result.scalar_one_or_none() is not None


def transition_tenant_if_version_matches(
    session: Session,
    *,
    tenant_id: UUID,
    version: int,
    current_statuses: tuple[TenantStatus, ...],
    new_status: TenantStatus,
) -> bool:
    result = session.execute(
        update(Tenant)
        .where(
            Tenant.id == tenant_id,
            Tenant.version == version,
            Tenant.status.in_(current_statuses),
        )
        .values(
            status=new_status,
            version=Tenant.version + 1,
            updated_at=utc_now(),
        )
        .returning(Tenant.id)
    )
    return result.scalar_one_or_none() is not None
