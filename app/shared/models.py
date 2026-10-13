from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator, Uuid

from app.shared.db import Base
from app.shared.state import TaskStatus, TaskType, TenantStatus
from app.shared.time import utc_now


class JsonDocument(TypeDecorator[dict[str, Any]]):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())

        return dialect.type_descriptor(JSON())


def enum_values(enum_type: type[TenantStatus] | type[TaskType] | type[TaskStatus]) -> list[str]:
    return [member.value for member in enum_type]


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("length(slug) BETWEEN 3 AND 28", name="tenant_slug_length"),
        CheckConstraint(
            "slug ~ '^[a-z][-a-z0-9]{1,26}[a-z0-9]$'",
            name="tenant_slug_format",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint("length(name) > 0", name="tenant_name_not_empty"),
        CheckConstraint("version >= 1", name="tenant_version_positive"),
        UniqueConstraint("slug", name="uq_tenants_slug"),
        Index("ix_tenants_status_created_at", "status", "created_at"),
        Index("ix_tenants_created_at_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(28), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(
            TenantStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="tenant_status",
        ),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="tenant")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_tasks_status_created_at", "status", "created_at"),
        Index("ix_tasks_type_created_at", "type", "created_at"),
        Index("ix_tasks_created_at_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    type: Mapped[TaskType] = mapped_column(
        Enum(
            TaskType,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="task_type",
        ),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(
            TaskStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="task_status",
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    tenant: Mapped[Tenant] = relationship(back_populates="tasks")


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_events_published_at_created_at", "published_at", "created_at"),
        Index("ix_outbox_events_created_at_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange: Mapped[str] = mapped_column(String(255), nullable=False)
    routing_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonDocument, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProcessedWorkerUpdate(Base):
    __tablename__ = "processed_worker_updates"
    __table_args__ = (
        Index("ix_processed_worker_updates_task_id_received_at", "task_id", "received_at"),
    )

    idempotency_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    task_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("tasks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
