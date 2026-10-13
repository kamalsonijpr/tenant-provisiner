from fastapi import FastAPI

from app.control_plane.api.errors import register_exception_handlers
from app.control_plane.api.tenants import router as tenants_router
from app.shared.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    register_exception_handlers(app)
    app.include_router(tenants_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
