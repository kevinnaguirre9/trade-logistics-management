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

    # Message broker
    rabbitmq_url: str = "amqp://trade_logistics:change_me@localhost:5672/"
    rabbitmq_app_name: str = "trade-logistics-management"
    rabbitmq_heartbeat: int = 30

    # Broker topology. Every value can be overridden per worker on the CLI.
    rabbitmq_primary_exchange: str = "trade-logistics.topic"
    rabbitmq_primary_exchange_type: str = "topic"
    rabbitmq_primary_queue: str = "trade-logistics.default"
    rabbitmq_primary_binding_key: str = "trade-logistics.#"

    rabbitmq_retry_exchange: str = "trade-logistics.retry"
    rabbitmq_retry_exchange_type: str = "topic"
    rabbitmq_retry_queue: str = "trade-logistics.default.retry"
    rabbitmq_retry_binding_key: str = "trade-logistics.default.retry"
    rabbitmq_retry_message_ttl_ms: int = 10_000

    rabbitmq_error_exchange: str = "trade-logistics.error"
    rabbitmq_error_exchange_type: str = "topic"
    rabbitmq_error_queue: str = "trade-logistics.error"
    rabbitmq_error_routing_key: str = "trade-logistics.dead-letter"

    rabbitmq_immediate_retries: int = 3
    rabbitmq_delayed_retries: int = 3
    rabbitmq_dispatch_limit: int = 10
    rabbitmq_consume_limit: int = 10

    @property
    def is_production(self) -> bool:
        """Return ``True`` when running with production semantics."""
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
