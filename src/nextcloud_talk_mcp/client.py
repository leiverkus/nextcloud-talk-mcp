"""HTTP client for the Nextcloud Talk (Spreed) OCS API."""

from __future__ import annotations

import random
import time
from typing import Any

import httpx

from nextcloud_talk_mcp import __version__
from nextcloud_talk_mcp.config import Settings
from nextcloud_talk_mcp.errors import (
    NextcloudAuthError,
    NextcloudNotFoundError,
    NextcloudOCSError,
    NextcloudTransportError,
)

_RETRY_STATUSES = {500, 502, 503, 504}
_IDEMPOTENT_METHODS = {"GET", "HEAD", "OPTIONS", "DELETE"}


class OCSClient:
    """Thin wrapper around httpx.Client for the Spreed OCS API.

    Auth via Basic Auth (app password). OCS responses are unwrapped and
    `ocs.meta.statuscode` is mapped to typed exceptions — Talk often returns
    HTTP 200 with an OCS error code.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        timeout: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self._settings = settings
        self._max_retries = max_retries
        self._base = f"{settings.nc_url}/ocs/v2.php/apps/spreed"
        self._client = httpx.Client(
            auth=httpx.BasicAuth(settings.nc_user, settings.nc_app_password),
            headers={
                "OCS-APIRequest": "true",
                "Accept": "application/json",
                "User-Agent": f"nextcloud-talk-mcp/{__version__}",
            },
            timeout=timeout,
        )

    def __enter__(self) -> OCSClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, *, data: dict[str, Any] | None = None) -> Any:
        return self.request("POST", path, data=data)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base}{path}"
        retriable = method.upper() in _IDEMPOTENT_METHODS
        last_transport_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.request(method, url, params=params, data=data)
            except httpx.TransportError as exc:
                last_transport_exc = exc
                if retriable and attempt < self._max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise NextcloudTransportError(f"transport error: {exc}") from exc

            if resp.status_code in _RETRY_STATUSES and retriable and attempt < self._max_retries:
                self._sleep_backoff(attempt)
                continue

            return self._handle_response(resp)

        # Defensive: loop always returns or raises above.
        raise NextcloudTransportError(f"request failed after retries: {last_transport_exc!r}")

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        time.sleep(0.5 * (2**attempt) + random.uniform(0, 0.25))

    @staticmethod
    def _handle_response(resp: httpx.Response) -> Any:
        if resp.status_code == 401:
            raise NextcloudAuthError("authentication failed (HTTP 401) — check NC_USER and NC_APP_PASSWORD")
        if resp.status_code == 404:
            raise NextcloudNotFoundError(f"not found (HTTP 404): {resp.request.url}")
        if resp.status_code >= 400:
            raise NextcloudOCSError(resp.status_code, f"HTTP {resp.status_code}: {resp.text[:200]}")

        try:
            payload = resp.json()
        except ValueError as exc:
            raise NextcloudOCSError(resp.status_code, f"non-JSON response: {exc}") from exc

        try:
            ocs = payload["ocs"]
            meta = ocs["meta"]
            statuscode = int(meta["statuscode"])
        except (KeyError, TypeError, ValueError) as exc:
            raise NextcloudOCSError(resp.status_code, f"unexpected OCS envelope: {payload!r}") from exc

        if statuscode in (100, 200):
            return ocs.get("data")
        if statuscode == 401:
            raise NextcloudAuthError(meta.get("message", "OCS authentication failed"))
        if statuscode == 404:
            raise NextcloudNotFoundError(meta.get("message", "OCS resource not found"))
        raise NextcloudOCSError(statuscode, meta.get("message", ""))
