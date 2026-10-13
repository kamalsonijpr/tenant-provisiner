from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.shared.state import TaskStatus, TaskType, TenantStatus
from app.shared.time import format_utc_millis

SLUG_PATTERN = r"^[a-z][-a-z0-9]{1,26}[a-z0-9]$"


class TenantCreate(BaseModel):
    slug: str = Field(min_length=3, max_length=28, pattern=SLUG_PATTERN)
    name: str = Field(min_length=1, max_length=255)


class TenantUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    version: int = Field(ge=1)


class TenantDelete(BaseModel):
    version: int = Field(ge=1)


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    status: TenantStatus
    version: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamps(self, value: datetime) -> str:
        return format_utc_millis(value)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: TaskType
    tenant_id: UUID
    status: TaskStatus
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamps(self, value: datetime) -> str:
        return format_utc_millis(value)


class PaginationParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = None


class PaginatedResponse[ItemT](BaseModel):
    items: list[ItemT]
    next_cursor: str | None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail
