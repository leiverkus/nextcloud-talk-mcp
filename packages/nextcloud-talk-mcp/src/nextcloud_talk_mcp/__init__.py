"""Nextcloud Talk MCP server — thin wrapper over nextcloud-talk-core."""

# Re-export the core exception hierarchy for convenience; the canonical
# definitions live in nextcloud_talk_core.errors.
from nextcloud_talk_core import (
    NextcloudAuthError,
    NextcloudConfigError,
    NextcloudNotFoundError,
    NextcloudOCSError,
    NextcloudTalkError,
    NextcloudTransportError,
)

__version__ = "1.0.2"

__all__ = [
    "NextcloudAuthError",
    "NextcloudConfigError",
    "NextcloudNotFoundError",
    "NextcloudOCSError",
    "NextcloudTalkError",
    "NextcloudTransportError",
    "__version__",
]
