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


# --- wait_for_messages (long-poll) ----------------------------------------


def test_wait_for_messages_params(wired):
    rec = wired(ocs_response(200, data=[{"id": 7, "actorDisplayName": "Al", "timestamp": 9, "message": "new"}]))
    result = server.wait_for_messages("tok1", last_known_message_id=5, limit=50, timeout=10)
    assert result == [{"id": 7, "actor": "Al", "timestamp": 9, "message": "new"}]
    url = str(rec.last.url)
    assert "/api/v1/chat/tok1" in url
    assert "lookIntoFuture=1" in url
    assert "lastKnownMessageId=5" in url
    assert "timeout=10" in url


def test_wait_for_messages_empty_returns_list(wired):
    wired(ocs_response(200, data=None))
    assert server.wait_for_messages("tok1", last_known_message_id=5, timeout=1) == []


def test_wait_for_messages_caps_timeout_and_limit(wired):
    rec = wired(ocs_response(200, data=[]))
    server.wait_for_messages("tok1", last_known_message_id=1, limit=999, timeout=999)
    url = str(rec.last.url)
    assert "timeout=60" in url
    assert "limit=200" in url


# --- edit_message / delete_message ----------------------------------------


def test_edit_message_uses_put(wired):
    rec = wired(ocs_response(200, data={"id": 42, "message": "edited"}))
    result = server.edit_message("tok1", 42, "edited")
    assert result == {"id": 42, "message": "edited"}
    assert rec.last.method == "PUT"
    assert "/api/v1/chat/tok1/42" in str(rec.last.url)
    assert b"message=edited" in rec.last.content


def test_delete_message_uses_delete(wired):
    rec = wired(ocs_response(200, data={"systemMessage": "message_deleted"}))
    result = server.delete_message("tok1", 42)
    assert result["id"] == 42
    assert result["deleted"] is True
    assert rec.last.method == "DELETE"
    assert "/api/v1/chat/tok1/42" in str(rec.last.url)


# --- read-markers ----------------------------------------------------------


def test_mark_as_read_with_id(wired):
    rec = wired(ocs_response(200, data={}))
    result = server.mark_as_read("tok1", last_read_message=99)
    assert result == {"token": "tok1", "read": True}
    assert rec.last.method == "POST"
    assert "/api/v1/chat/tok1/read" in str(rec.last.url)
    assert b"lastReadMessage=99" in rec.last.content


def test_mark_as_read_without_id(wired):
    rec = wired(ocs_response(200, data={}))
    server.mark_as_read("tok1")
    assert b"lastReadMessage" not in rec.last.content


def test_mark_as_unread_uses_delete(wired):
    rec = wired(ocs_response(200, data={}))
    result = server.mark_as_unread("tok1")
    assert result == {"token": "tok1", "unread": True}
    assert rec.last.method == "DELETE"
    assert "/api/v1/chat/tok1/read" in str(rec.last.url)


# --- conversation management ----------------------------------------------


def test_create_conversation_group(wired):
    rec = wired(ocs_response(200, data={"token": "newtok", "displayName": "Team", "type": 2}))
    result = server.create_conversation(room_type=2, room_name="Team")
    assert result == {"token": "newtok", "name": "Team", "type": 2}
    assert rec.last.method == "POST"
    assert str(rec.last.url).endswith("/api/v4/room")
    assert b"roomType=2" in rec.last.content
    assert b"roomName=Team" in rec.last.content


def test_create_conversation_one_to_one_with_invite(wired):
    rec = wired(ocs_response(200, data={"token": "t", "displayName": "Bob", "type": 1}))
    server.create_conversation(room_type=1, invite="bob")
    assert b"invite=bob" in rec.last.content


def test_rename_conversation_uses_put(wired):
    rec = wired(ocs_response(200, data={}))
    result = server.rename_conversation("tok1", "New Name")
    assert result == {"token": "tok1", "name": "New Name"}
    assert rec.last.method == "PUT"
    assert str(rec.last.url).endswith("/api/v4/room/tok1")
    assert b"roomName=New+Name" in rec.last.content


def test_set_description_uses_put(wired):
    rec = wired(ocs_response(200, data={}))
    result = server.set_description("tok1", "desc text")
    assert result == {"token": "tok1", "description": "desc text"}
    assert rec.last.method == "PUT"
    assert "/api/v4/room/tok1/description" in str(rec.last.url)
    assert b"description=desc+text" in rec.last.content


def test_delete_conversation_uses_delete(wired):
    rec = wired(ocs_response(200, data={}))
    result = server.delete_conversation("tok1")
    assert result == {"token": "tok1", "deleted": True}
    assert rec.last.method == "DELETE"
    assert str(rec.last.url).endswith("/api/v4/room/tok1")


# --- participant management ------------------------------------------------


def test_list_participants_schema(wired):
    rec = wired(
        ocs_response(
            200,
            data=[
                {
                    "attendeeId": 11,
                    "actorId": "alice",
                    "displayName": "Alice",
                    "participantType": 1,
                    "permissions": 254,
                }
            ],
        )
    )
    result = server.list_participants("tok1")
    assert result == [
        {
            "attendeeId": 11,
            "actorId": "alice",
            "displayName": "Alice",
            "participantType": 1,
            "permissions": 254,
        }
    ]
    assert "/api/v4/room/tok1/participants" in str(rec.last.url)


def test_add_participant_default_source(wired):
    rec = wired(ocs_response(200, data={"type": 3}))
    result = server.add_participant("tok1", "bob")
    assert result["added"] == "bob"
    assert result["source"] == "users"
    assert rec.last.method == "POST"
    assert "/api/v4/room/tok1/participants" in str(rec.last.url)
    assert b"newParticipant=bob" in rec.last.content
    assert b"source=users" in rec.last.content


def test_add_participant_group_source(wired):
    rec = wired(ocs_response(200, data={}))
    server.add_participant("tok1", "staff", source="groups")
    assert b"source=groups" in rec.last.content


def test_remove_participant_sends_attendee_id_in_body(wired):
    rec = wired(ocs_response(200, data={}))
    result = server.remove_participant("tok1", 11)
    assert result == {"token": "tok1", "removed_attendee": 11}
    assert rec.last.method == "DELETE"
    assert "/api/v4/room/tok1/attendees" in str(rec.last.url)
    assert b"attendeeId=11" in rec.last.content


def test_set_participant_permissions_builds_bitmask(wired):
    rec = wired(ocs_response(200, data={}))
    result = server.set_participant_permissions(
        "tok1",
        11,
        can_publish_audio=True,
        can_publish_video=True,
        can_post_chat=True,
    )
    # 16 | 32 | 128 = 176, plus custom bit 1 = 177
    assert result["permissions"] == 177
    assert rec.last.method == "PUT"
    assert "/api/v4/room/tok1/attendees/permissions" in str(rec.last.url)
    assert b"attendeeId=11" in rec.last.content
    assert b"method=set" in rec.last.content
    assert b"permissions=177" in rec.last.content


def test_set_participant_permissions_no_flags_is_zero(wired):
    rec = wired(ocs_response(200, data={}))
    result = server.set_participant_permissions("tok1", 11, mode="set")
    assert result["permissions"] == 0
    assert b"permissions=0" in rec.last.content


def test_set_participant_permissions_mode_remove(wired):
    rec = wired(ocs_response(200, data={}))
    server.set_participant_permissions("tok1", 11, mode="remove", can_start_call=True)
    assert b"method=remove" in rec.last.content
