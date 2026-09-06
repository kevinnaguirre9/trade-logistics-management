"""Application settings loaded from environment variables (12-factor)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated view over the process environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Trade Logistics Management"
    app_env: str = "development"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_log_level: str = "info"

    # Database
    database_url: str = Field(
        default=(
            "postgresql+asyncpg://trade_logistics:change_me"
            "@localhost:5432/trade_logistics"
        ),
    )
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Module schemas
    shipment_schema: str = "shipment"
    customs_schema: str = "customs"

    # Message broker (wiring deferred).
    rabbitmq_url: str = "amqp://trade_logistics:change_me@localhost:5672/"

    @property
    def is_production(self) -> bool:
        """Return ``True`` when running with production semantics."""
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
