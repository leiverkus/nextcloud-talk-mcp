"""Exception hierarchy for the Nextcloud Talk MCP server."""

from __future__ import annotations


class NextcloudTalkError(Exception):
    """Base class for all errors raised by this package."""


class NextcloudConfigError(NextcloudTalkError):
    """Raised when required configuration (env vars) is missing or invalid."""


class NextcloudAuthError(NextcloudTalkError):
    """Raised on HTTP 401 or OCS statuscode 401 — wrong user / app password."""


class NextcloudNotFoundError(NextcloudTalkError):
    """Raised on HTTP 404 or OCS statuscode 404 — room or message not found."""


class NextcloudOCSError(NextcloudTalkError):
    """Raised when the OCS envelope reports any other error statuscode."""

    def __init__(self, statuscode: int, message: str) -> None:
        super().__init__(f"OCS error {statuscode}: {message}")
        self.statuscode = statuscode
        self.message = message


class NextcloudTransportError(NextcloudTalkError):
    """Raised when the HTTP transport fails after all retries are exhausted."""
