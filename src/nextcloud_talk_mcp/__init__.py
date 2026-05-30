"""Nextcloud Talk MCP server — Spreed OCS API wrapper."""

from nextcloud_talk_mcp.errors import (
    NextcloudAuthError,
    NextcloudConfigError,
    NextcloudNotFoundError,
    NextcloudOCSError,
    NextcloudTalkError,
    NextcloudTransportError,
)

__version__ = "0.1.0"

__all__ = [
    "NextcloudAuthError",
    "NextcloudConfigError",
    "NextcloudNotFoundError",
    "NextcloudOCSError",
    "NextcloudTalkError",
    "NextcloudTransportError",
    "__version__",
]
