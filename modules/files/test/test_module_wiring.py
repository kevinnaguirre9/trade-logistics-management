"""The Files module exposes a router and maps its objects once."""

from fastapi import APIRouter

from modules.files.src.api import router
from modules.files.src.infrastructure.database import SCHEMA
from modules.files.src.infrastructure.database.entities import start_mappers
from modules.files.src.infrastructure.storage import build_disk_registry
from modules.shared.config import Settings


def test_module_publishes_a_router() -> None:
    assert isinstance(router, APIRouter)


def test_module_owns_its_own_schema() -> None:
    assert SCHEMA == "files"


def test_start_mappers_is_idempotent() -> None:
    start_mappers()
    start_mappers()


class TestDiskRegistry:
    def test_always_offers_the_local_disk(self) -> None:
        disks = build_disk_registry(Settings(_env_file=None))

        assert list(disks) == ["local"]
        assert disks["local"].protocol == "file"

    def test_offers_a_cloud_disk_once_its_bucket_is_configured(self) -> None:
        disks = build_disk_registry(
            Settings(
                _env_file=None,
                files_aws_bucket="trade-logistics-docs",
                files_aws_region="eu-west-1",
            )
        )

        assert disks["aws"].protocol == "s3"
        assert disks["aws"].root == "trade-logistics-docs"
        assert disks["aws"].options["client_kwargs"]["region_name"] == "eu-west-1"

    def test_reads_the_gcp_service_account_from_a_path(self) -> None:
        disks = build_disk_registry(
            Settings(
                _env_file=None,
                files_gcp_bucket="trade-logistics-docs",
                files_gcp_credentials_path="/run/secrets/gcp.json",
            )
        )

        assert disks["gcp"].options["token"] == "/run/secrets/gcp.json"

    def test_leaves_the_aws_credential_chain_alone_when_no_key_is_set(self) -> None:
        disks = build_disk_registry(
            Settings(_env_file=None, files_aws_bucket="trade-logistics-docs")
        )

        assert "key" not in disks["aws"].options
        assert "secret" not in disks["aws"].options
