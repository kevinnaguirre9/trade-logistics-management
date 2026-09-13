"""The disks this deployment can write to, assembled from the environment.

A disk is a name the caller uses (``"local"``, ``"gcp"``, ``"aws"``,
``"sftp"``) bound to an fsspec protocol, a root the module never writes above,
and whatever credentials that protocol needs. A cloud disk only appears in the
registry once its bucket or host is configured, so an unconfigured backend is
rejected with a clear error instead of failing halfway through an upload.
"""

from dataclasses import dataclass, field
from typing import Any

from modules.shared.config import Settings

#: Disk names the module knows how to configure.
LOCAL_DISK = "local"
GCP_DISK = "gcp"
AWS_DISK = "aws"
SFTP_DISK = "sftp"


@dataclass(frozen=True, slots=True)
class DiskConfig:
    """One storage class, resolved from settings."""

    name: str
    protocol: str
    #: Bucket name, or the directory every key is written under.
    root: str
    #: Passed straight to ``fsspec.filesystem(protocol, **options)``.
    options: dict[str, Any] = field(default_factory=dict)
    #: The pip extra that ships the driver, named in the error when it is
    #: missing from the image.
    extra: str | None = None


def build_disk_registry(settings: Settings) -> dict[str, DiskConfig]:
    """Return every disk this process can serve, keyed by name."""
    disks: dict[str, DiskConfig] = {
        LOCAL_DISK: DiskConfig(
            name=LOCAL_DISK,
            protocol="file",
            root=settings.files_local_root,
            # auto_mkdir keeps a first upload from failing on a missing folder.
            options={"auto_mkdir": True},
        )
    }

    if settings.files_gcp_bucket:
        gcp_options: dict[str, Any] = {}
        if settings.files_gcp_project:
            gcp_options["project"] = settings.files_gcp_project
        if settings.files_gcp_credentials_path:
            # gcsfs reads a service account JSON file straight from a path.
            gcp_options["token"] = settings.files_gcp_credentials_path
        disks[GCP_DISK] = DiskConfig(
            name=GCP_DISK,
            protocol="gcs",
            root=settings.files_gcp_bucket,
            options=gcp_options,
            extra="gcp",
        )

    if settings.files_aws_bucket:
        client_kwargs: dict[str, Any] = {}
        if settings.files_aws_region:
            client_kwargs["region_name"] = settings.files_aws_region
        if settings.files_aws_endpoint_url:
            # Set for S3-compatible storage (MinIO, Ceph, LocalStack).
            client_kwargs["endpoint_url"] = settings.files_aws_endpoint_url

        aws_options: dict[str, Any] = {"client_kwargs": client_kwargs}
        # Left unset, s3fs falls back to the standard credential chain
        # (instance role, ~/.aws, AWS_* variables), which is what a deployed
        # service should normally use.
        if settings.files_aws_access_key_id:
            aws_options["key"] = settings.files_aws_access_key_id
        if settings.files_aws_secret_access_key:
            aws_options["secret"] = settings.files_aws_secret_access_key

        disks[AWS_DISK] = DiskConfig(
            name=AWS_DISK,
            protocol="s3",
            root=settings.files_aws_bucket,
            options=aws_options,
            extra="aws",
        )

    if settings.files_sftp_host:
        sftp_options: dict[str, Any] = {
            "host": settings.files_sftp_host,
            "port": settings.files_sftp_port,
        }
        if settings.files_sftp_username:
            sftp_options["username"] = settings.files_sftp_username
        if settings.files_sftp_password:
            sftp_options["password"] = settings.files_sftp_password
        if settings.files_sftp_private_key_path:
            sftp_options["key_filename"] = settings.files_sftp_private_key_path

        disks[SFTP_DISK] = DiskConfig(
            name=SFTP_DISK,
            protocol="sftp",
            root=settings.files_sftp_root,
            options=sftp_options,
            extra="sftp",
        )

    return disks
