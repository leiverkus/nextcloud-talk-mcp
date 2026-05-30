"""Shared test fixtures: OCSClient backed by a recording MockTransport."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from nextcloud_talk_core.client import OCSClient
from nextcloud_talk_core.config import Settings
from nextcloud_talk_core.talk import TalkClient

SETTINGS = Settings(nc_url="https://nc.example", nc_user="alice", nc_app_password="app-pw")


def ocs_response(statuscode: int, data=None, message: str = "", *, http_status: int = 200) -> httpx.Response:
    """Build an httpx.Response wrapping an OCS v2 envelope."""
    return httpx.Response(
        http_status,
        json={"ocs": {"meta": {"status": "ok", "statuscode": statuscode, "message": message}, "data": data}},
    )


class Recorder:
    """Captures every request sent through the mock transport."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]


@pytest.fixture
def make_client(monkeypatch):
    """Factory: build an OCSClient whose transport is driven by `handler`.

    `handler` may be a single httpx.Response, a list (consumed in order), or a
    callable(request) -> httpx.Response. Returns (client, recorder).
    """
    # Never actually sleep during retry tests.
    monkeypatch.setattr("nextcloud_talk_core.client.time.sleep", lambda *_: None)

    created: list[OCSClient] = []

    def _factory(handler, **kwargs) -> tuple[OCSClient, Recorder]:
        recorder = Recorder()

        if isinstance(handler, httpx.Response):
            responses = [handler]
            handler_fn: Callable[[httpx.Request], httpx.Response] | None = None
        elif isinstance(handler, list):
            responses = list(handler)
            handler_fn = None
        else:
            responses = []
            handler_fn = handler

        def dispatch(request: httpx.Request) -> httpx.Response:
            recorder.requests.append(request)
            if handler_fn is not None:
                return handler_fn(request)
            return responses.pop(0)

        client = OCSClient(SETTINGS, **kwargs)
        client._client = httpx.Client(
            transport=httpx.MockTransport(dispatch),
            headers=client._client.headers,
        )
        created.append(client)
        return client, recorder

    yield _factory

    for c in created:
        c.close()


@pytest.fixture
def make_talk(make_client):
    """Factory: build a TalkClient whose underlying OCSClient is mock-backed.

    Returns (talk, recorder); `handler` is the same as for make_client.
    """

    def _factory(handler, **kwargs) -> tuple[TalkClient, Recorder]:
        client, recorder = make_client(handler, **kwargs)
        talk = TalkClient.__new__(TalkClient)
        talk._ocs = client
        return talk, recorder

    return _factory
