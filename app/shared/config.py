from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    app_name: str = Field(default="Tenant Provisioning Control Plane")
    database_url: str = Field(
        default="postgresql+psycopg://tenant_provisioner:tenant_provisioner@localhost:5432/"
        "tenant_provisioner"
    )
    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()
