"""Tests for OCSClient: OCS envelope parsing, error mapping, retries."""

from __future__ import annotations

import httpx
import pytest

from nextcloud_talk_mcp.errors import (
    NextcloudAuthError,
    NextcloudNotFoundError,
    NextcloudOCSError,
    NextcloudTransportError,
)

from .conftest import ocs_response

# --- success / parsing ----------------------------------------------------


def test_get_unwraps_ocs_data(make_client):
    client, rec = make_client(ocs_response(200, data=[{"token": "t1"}]))
    assert client.get("/api/v4/room") == [{"token": "t1"}]
    assert rec.last.method == "GET"
    assert str(rec.last.url).endswith("/ocs/v2.php/apps/spreed/api/v4/room")


def test_statuscode_100_is_success(make_client):
    client, _ = make_client(ocs_response(100, data={"ok": True}))
    assert client.get("/api/v4/room") == {"ok": True}


def test_request_sets_ocs_header(make_client):
    client, rec = make_client(ocs_response(200, data=[]))
    client.get("/api/v4/room")
    assert rec.last.headers["OCS-APIRequest"] == "true"


def test_post_sends_body(make_client):
    client, rec = make_client(ocs_response(200, data={"id": 7}))
    client.post("/api/v1/chat/abc", data={"message": "hi"})
    assert rec.last.method == "POST"
    assert b"message=hi" in rec.last.content


# --- OCS error codes on HTTP 200 -----------------------------------------


def test_ocs_401_maps_to_auth_error(make_client):
    client, _ = make_client(ocs_response(401, message="no auth"))
    with pytest.raises(NextcloudAuthError, match="no auth"):
        client.get("/api/v4/room")


def test_ocs_404_maps_to_not_found(make_client):
    client, _ = make_client(ocs_response(404, message="gone"))
    with pytest.raises(NextcloudNotFoundError, match="gone"):
        client.get("/api/v1/chat/x")


def test_ocs_403_maps_to_generic_ocs_error(make_client):
    client, _ = make_client(ocs_response(403, message="forbidden"))
    with pytest.raises(NextcloudOCSError) as exc:
        client.get("/api/v1/chat/x/mentions")
    assert exc.value.statuscode == 403
    assert exc.value.message == "forbidden"


# --- raw HTTP error statuses ---------------------------------------------


def test_http_401_maps_to_auth_error(make_client):
    client, _ = make_client(httpx.Response(401, text="unauthorized"))
    with pytest.raises(NextcloudAuthError):
        client.get("/api/v4/room")


def test_http_404_maps_to_not_found(make_client):
    client, _ = make_client(httpx.Response(404, text="nope"))
    with pytest.raises(NextcloudNotFoundError):
        client.get("/api/v4/room")


def test_http_400_maps_to_ocs_error(make_client):
    client, _ = make_client(httpx.Response(400, text="bad request"))
    with pytest.raises(NextcloudOCSError) as exc:
        client.get("/api/v4/room")
    assert exc.value.statuscode == 400


def test_non_json_body_raises_ocs_error(make_client):
    client, _ = make_client(httpx.Response(200, text="<html>not json</html>"))
    with pytest.raises(NextcloudOCSError, match="non-JSON"):
        client.get("/api/v4/room")


def test_unexpected_envelope_raises_ocs_error(make_client):
    client, _ = make_client(httpx.Response(200, json={"unexpected": True}))
    with pytest.raises(NextcloudOCSError, match="unexpected OCS envelope"):
        client.get("/api/v4/room")


# --- retries --------------------------------------------------------------


def test_get_retries_transient_5xx_then_succeeds(make_client):
    responses = [
        httpx.Response(503, text="busy"),
        httpx.Response(502, text="busy"),
        ocs_response(200, data=["ok"]),
    ]
    client, rec = make_client(responses, max_retries=2)
    assert client.get("/api/v4/room") == ["ok"]
    assert len(rec.requests) == 3  # two retries + success


def test_get_gives_up_after_max_retries(make_client):
    responses = [httpx.Response(503) for _ in range(3)]
    client, rec = make_client(responses, max_retries=2)
    with pytest.raises(NextcloudOCSError) as exc:
        client.get("/api/v4/room")
    assert exc.value.statuscode == 503
    assert len(rec.requests) == 3  # 1 initial + 2 retries


def test_transport_error_retried_then_raised(make_client):
    def boom(_request):
        raise httpx.ConnectError("connection refused")

    client, rec = make_client(boom, max_retries=2)
    with pytest.raises(NextcloudTransportError, match="transport error"):
        client.get("/api/v4/room")
    assert len(rec.requests) == 3


def test_post_is_not_retried_on_5xx(make_client):
    responses = [httpx.Response(503), ocs_response(200, data={"id": 1})]
    client, rec = make_client(responses, max_retries=2)
    with pytest.raises(NextcloudOCSError):
        client.post("/api/v1/chat/abc", data={"message": "hi"})
    assert len(rec.requests) == 1  # POST not retried


def test_4xx_not_retried(make_client):
    responses = [httpx.Response(404), ocs_response(200, data=[])]
    client, rec = make_client(responses, max_retries=2)
    with pytest.raises(NextcloudNotFoundError):
        client.get("/api/v4/room")
    assert len(rec.requests) == 1


# --- context manager ------------------------------------------------------


def test_context_manager_closes(make_client):
    client, _ = make_client(ocs_response(200, data=[]))
    with client as c:
        assert c.get("/api/v4/room") == []
    assert client._client.is_closed
