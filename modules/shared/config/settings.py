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
    files_schema: str = "files"

    # -- Files -------------------------------------------------------------
    # Disk the caller gets when it names none, and the ceiling every upload is
    # measured against while it streams.
    files_default_disk: str = "local"
    files_max_upload_bytes: int = 25 * 1024 * 1024

    # local: a directory in the container, normally a mounted volume.
    files_local_root: str = "/app/storage"

    # Google Cloud Storage. The bucket is what switches the disk on; the
    # service account JSON is read from the path given here, so the key file is
    # mounted rather than baked into the image.
    files_gcp_bucket: str = ""
    files_gcp_project: str = ""
    files_gcp_credentials_path: str = ""

    # AWS S3, or anything that speaks its API (MinIO, Ceph) through the
    # endpoint URL. Leave the key pair empty to use the standard credential
    # chain: instance role, ~/.aws, AWS_* variables.
    files_aws_bucket: str = ""
    files_aws_region: str = "us-east-1"
    files_aws_access_key_id: str = ""
    files_aws_secret_access_key: str = ""
    files_aws_endpoint_url: str = ""

    # SFTP. Either a password or a private key file, not both.
    files_sftp_host: str = ""
    files_sftp_port: int = 22
    files_sftp_username: str = ""
    files_sftp_password: str = ""
    files_sftp_private_key_path: str = ""
    files_sftp_root: str = ""

    # Message broker
    rabbitmq_url: str = "amqp://trade_logistics:change_me@localhost:5672/"
    rabbitmq_app_name: str = "trade-logistics-management"
    rabbitmq_heartbeat: int = 30

    # Broker topology. Every value can be overridden per worker on the CLI.
    rabbitmq_primary_exchange: str = "trade-logistics.topic"
    rabbitmq_primary_exchange_type: str = "topic"
    rabbitmq_primary_queue: str = "trade-logistics.default"
    rabbitmq_primary_binding_key: str = "trade-logistics.#"

    # Direct, not topic: both hops of the retry path address exactly one queue,
    # which is why the exchange is named for its type rather than for retries.
    rabbitmq_retry_exchange: str = "trade-logistics.direct"
    rabbitmq_retry_exchange_type: str = "direct"
    rabbitmq_retry_queue: str = "trade-logistics.default.delayed-retry"
    rabbitmq_retry_binding_key: str = "trade-logistics.default.delayed-retry"
    rabbitmq_retry_message_ttl_ms: int = 10_000

    # The way back in for an expired retry. Left empty they are derived from
    # the primary queue, so each worker reclaims its own retries and no others.
    rabbitmq_retry_dead_letter_exchange: str = ""
    rabbitmq_retry_dead_letter_routing_key: str = ""
    rabbitmq_primary_retry_binding_exchange: str = ""
    rabbitmq_primary_retry_binding_key: str = ""

    # Also direct, and the same exchange: a message that has exhausted its
    # retries is parked in exactly one error queue, so there is nothing for a
    # topic exchange to fan out to.
    rabbitmq_error_exchange: str = "trade-logistics.direct"
    rabbitmq_error_exchange_type: str = "direct"
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
