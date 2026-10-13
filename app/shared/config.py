from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    app_name: str = Field(default="Tenant Provisioning Control Plane")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/tenant_provisioner"
    )
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/")
    outbox_batch_size: int = Field(default=50, ge=1)
    outbox_poll_interval_seconds: float = Field(default=2.0, gt=0)
    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()
