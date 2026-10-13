import uvicorn
from fastapi import FastAPI

from app.control_plane.api.errors import register_exception_handlers
from app.control_plane.api.tasks import router as tasks_router
from app.control_plane.api.tenants import router as tenants_router
from app.shared.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    register_exception_handlers(app)
    app.include_router(tenants_router)
    app.include_router(tasks_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "app.control_plane.api.main:app",
        host="0.0.0.0",  # nosec B104  # noqa: S104
        port=8000,
        reload=False,
    )
