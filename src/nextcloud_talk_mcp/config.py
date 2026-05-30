"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from nextcloud_talk_mcp.errors import NextcloudConfigError


@dataclass(frozen=True)
class Settings:
    nc_url: str
    nc_user: str
    nc_app_password: str

    @classmethod
    def from_env(cls) -> Settings:
        nc_url = os.environ.get("NC_URL", "").strip()
        nc_user = os.environ.get("NC_USER", "").strip()
        nc_app_password = os.environ.get("NC_APP_PASSWORD", "")

        if not nc_url:
            raise NextcloudConfigError(
                "NC_URL is not set. Set NC_URL to your Nextcloud base URL, e.g. https://cloud.example.com"
            )
        if not (nc_url.startswith("http://") or nc_url.startswith("https://")):
            raise NextcloudConfigError(f"NC_URL must start with http:// or https://, got {nc_url!r}")
        if not nc_user:
            raise NextcloudConfigError("NC_USER is not set. Set it to your Nextcloud username.")
        if not nc_app_password:
            raise NextcloudConfigError(
                "NC_APP_PASSWORD is not set. Create one under "
                "Settings → Security → App passwords and export it as NC_APP_PASSWORD."
            )

        return cls(
            nc_url=nc_url.rstrip("/"),
            nc_user=nc_user,
            nc_app_password=nc_app_password,
        )
