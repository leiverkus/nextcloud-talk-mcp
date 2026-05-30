"""Tests for the four MCP tools: return schema and endpoint/method choice.

FastMCP 3.x registers tools as plain callables — they are called directly.
The tests install a mock-backed OCSClient on the server's module global and
call each tool function to exercise real tool logic without the MCP layer.
"""

from __future__ import annotations

import httpx
import pytest

import nextcloud_talk_mcp.server as server
from nextcloud_talk_mcp.errors import NextcloudNotFoundError

from .conftest import ocs_response


@pytest.fixture
def wired(make_client):
    """Install a mock-backed client as the server's global; restore after."""
    previous = server._client

    def _wire(handler, **kwargs):
        client, rec = make_client(handler, **kwargs)
        server._client = client
        return rec

    yield _wire
    server._client = previous


# --- list_conversations ---------------------------------------------------


def test_list_conversations_schema(wired):
    rec = wired(
        ocs_response(
            200,
            data=[
                {
                    "token": "tok1",
                    "displayName": "Team",
                    "type": 2,
                    "unreadMessages": 5,
                    "lastMessage": {"message": "hello"},
                }
            ],
        )
    )
    result = server.list_conversations()
    assert result == [{"token": "tok1", "name": "Team", "type": 2, "unread": 5, "lastMessage": "hello"}]
    assert str(rec.last.url).endswith("/api/v4/room")


def test_list_conversations_handles_missing_fields(wired):
    wired(ocs_response(200, data=[{"token": "t", "displayName": "X", "type": 1}]))
    result = server.list_conversations()
    assert result == [{"token": "t", "name": "X", "type": 1, "unread": 0, "lastMessage": ""}]


def test_list_conversations_null_last_message(wired):
    wired(ocs_response(200, data=[{"token": "t", "displayName": "X", "type": 1, "lastMessage": None}]))
    assert server.list_conversations()[0]["lastMessage"] == ""


# --- read_messages --------------------------------------------------------


def test_read_messages_schema_and_params(wired):
    rec = wired(
        ocs_response(
            200,
            data=[{"id": 1, "actorDisplayName": "Alice", "timestamp": 1000, "message": "hi"}],
        )
    )
    result = server.read_messages("tok1", limit=5)
    assert result == [{"id": 1, "actor": "Alice", "timestamp": 1000, "message": "hi"}]
    url = str(rec.last.url)
    assert "/api/v1/chat/tok1" in url
    assert "lookIntoFuture=0" in url
    assert "limit=5" in url


def test_read_messages_actor_fallback(wired):
    wired(ocs_response(200, data=[{"id": 2, "actorId": "user42", "timestamp": 1, "message": "x"}]))
    assert server.read_messages("tok1")[0]["actor"] == "user42"


def test_read_messages_bad_token_raises(wired):
    wired(httpx.Response(404, text="no room"))
    with pytest.raises(NextcloudNotFoundError):
        server.read_messages("nope")


# --- send_message ---------------------------------------------------------


def test_send_message_posts_to_correct_endpoint(wired):
    rec = wired(ocs_response(200, data={"id": 99, "message": "sent text"}))
    result = server.send_message("tok1", "sent text")
    assert result == {"id": 99, "sent": "sent text"}
    assert rec.last.method == "POST"
    assert "/api/v1/chat/tok1" in str(rec.last.url)
    assert b"message=sent+text" in rec.last.content


def test_send_message_includes_reply_to(wired):
    rec = wired(ocs_response(200, data={"id": 5, "message": "re"}))
    server.send_message("tok1", "re", reply_to=42)
    assert b"replyTo=42" in rec.last.content


def test_send_message_omits_reply_to_when_none(wired):
    rec = wired(ocs_response(200, data={"id": 5, "message": "x"}))
    server.send_message("tok1", "x")
    assert b"replyTo" not in rec.last.content


# --- list_mentions --------------------------------------------------------


def test_list_mentions_schema(wired):
    rec = wired(
        ocs_response(
            200,
            data=[{"id": "bob", "label": "Bob", "source": "users"}],
        )
    )
    result = server.list_mentions("tok1", limit=10)
    assert result == [{"id": "bob", "label": "Bob", "source": "users"}]
    url = str(rec.last.url)
    assert "/api/v1/chat/tok1/mentions" in url
    assert "limit=10" in url
