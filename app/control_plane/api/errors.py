from typing import Any
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TenantNotFoundError(ApiError):
    status_code = 404
    code = "tenant_not_found"

    def __init__(self, tenant_id: UUID) -> None:
        super().__init__("Tenant not found.", {"tenant_id": str(tenant_id)})


class TenantAlreadyExistsError(ApiError):
    status_code = 409
    code = "tenant_already_exists"

    def __init__(self, slug: str) -> None:
        super().__init__("A tenant with this slug already exists.", {"slug": slug})


class TenantUpdateNotAllowedError(ApiError):
    status_code = 409
    code = "tenant_update_not_allowed"

    def __init__(self, status: str, operation: str) -> None:
        super().__init__(
            f"Tenant cannot be {operation} while in status '{status}'.",
            {"status": status, "operation": operation},
        )


class TenantVersionConflictError(ApiError):
    status_code = 409
    code = "tenant_version_conflict"

    def __init__(self, expected_version: int, actual_version: int) -> None:
        super().__init__(
            "Tenant version conflict.",
            {"expected_version": expected_version, "actual_version": actual_version},
        )


class TaskNotFoundError(ApiError):
    status_code = 404
    code = "task_not_found"

    def __init__(self, task_id: UUID) -> None:
        super().__init__("Task not found.", {"task_id": str(task_id)})


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_handler)
