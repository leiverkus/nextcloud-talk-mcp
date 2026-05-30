"""Tests for TalkClient: endpoint/method/payload choice and model mapping."""

from __future__ import annotations

import httpx
import pytest

from nextcloud_talk_core.errors import NextcloudNotFoundError
from nextcloud_talk_core.models import Conversation, Mention, Message, Participant, Reaction

from .conftest import ocs_response

# --- chat: read -----------------------------------------------------------


def test_list_conversations_returns_models(make_talk):
    talk, rec = make_talk(
        ocs_response(
            200,
            data=[
                {
                    "token": "t1",
                    "displayName": "Team",
                    "type": 2,
                    "unreadMessages": 5,
                    "lastMessage": {"message": "hello"},
                }
            ],
        )
    )
    result = talk.list_conversations()
    assert result == [Conversation(token="t1", name="Team", type=2, unread=5, last_message="hello")]
    assert str(rec.last.url).endswith("/api/v4/room")


def test_read_messages_returns_models_with_attachments(make_talk):
    talk, rec = make_talk(
        ocs_response(
            200,
            data=[
                {
                    "id": 1,
                    "actorDisplayName": "Alice",
                    "timestamp": 1000,
                    "message": "hi",
                    "messageParameters": {"file": {"type": "file", "name": "x.pdf"}},
                }
            ],
        )
    )
    msgs = talk.read_messages("t1", limit=5)
    assert isinstance(msgs[0], Message)
    assert msgs[0].id == 1 and msgs[0].actor == "Alice"
    assert msgs[0].attachments[0].name == "x.pdf"
    url = str(rec.last.url)
    assert "/api/v1/chat/t1" in url and "lookIntoFuture=0" in url and "limit=5" in url


def test_read_messages_actor_fallback(make_talk):
    talk, _ = make_talk(ocs_response(200, data=[{"id": 2, "actorId": "u42", "timestamp": 1, "message": "x"}]))
    assert talk.read_messages("t1")[0].actor == "u42"


def test_list_mentions_returns_models(make_talk):
    talk, rec = make_talk(ocs_response(200, data=[{"id": "bob", "label": "Bob", "source": "users"}]))
    assert talk.list_mentions("t1", limit=10) == [Mention(id="bob", label="Bob", source="users")]
    assert "/api/v1/chat/t1/mentions" in str(rec.last.url)


def test_wait_for_messages_params_and_caps(make_talk):
    talk, rec = make_talk(ocs_response(200, data=[{"id": 7, "actorId": "a", "timestamp": 9, "message": "n"}]))
    out = talk.wait_for_messages("t1", last_known_message_id=5, limit=999, timeout=999)
    assert out[0].id == 7
    url = str(rec.last.url)
    assert "lookIntoFuture=1" in url and "lastKnownMessageId=5" in url
    assert "timeout=60" in url and "limit=200" in url  # capped


def test_wait_for_messages_empty(make_talk):
    talk, _ = make_talk(ocs_response(200, data=None))
    assert talk.wait_for_messages("t1", last_known_message_id=5) == []


# --- chat: write ----------------------------------------------------------


def test_send_message_returns_model(make_talk):
    talk, rec = make_talk(ocs_response(200, data={"id": 99, "actorId": "a", "timestamp": 1, "message": "sent"}))
    msg = talk.send_message("t1", "sent")
    assert msg.id == 99 and msg.message == "sent"
    assert rec.last.method == "POST"
    assert b"message=sent" in rec.last.content


def test_send_message_reply_to(make_talk):
    talk, rec = make_talk(ocs_response(200, data={"id": 5, "actorId": "a", "timestamp": 1, "message": "re"}))
    talk.send_message("t1", "re", reply_to=42)
    assert b"replyTo=42" in rec.last.content


def test_edit_message_uses_put(make_talk):
    talk, rec = make_talk(ocs_response(200, data={"id": 42, "actorId": "a", "timestamp": 1, "message": "ed"}))
    assert talk.edit_message("t1", 42, "ed").message == "ed"
    assert rec.last.method == "PUT"
    assert "/api/v1/chat/t1/42" in str(rec.last.url)


def test_delete_message_returns_system_message(make_talk):
    talk, rec = make_talk(ocs_response(200, data={"systemMessage": "message_deleted"}))
    assert talk.delete_message("t1", 42) == "message_deleted"
    assert rec.last.method == "DELETE"


def test_read_messages_bad_token_raises(make_talk):
    talk, _ = make_talk(httpx.Response(404, text="no room"))
    with pytest.raises(NextcloudNotFoundError):
        talk.read_messages("nope")


# --- read-markers ---------------------------------------------------------


def test_mark_as_read_with_id(make_talk):
    talk, rec = make_talk(ocs_response(200, data={}))
    talk.mark_as_read("t1", last_read_message=99)
    assert rec.last.method == "POST"
    assert "/api/v1/chat/t1/read" in str(rec.last.url)
    assert b"lastReadMessage=99" in rec.last.content


def test_mark_as_read_without_id(make_talk):
    talk, rec = make_talk(ocs_response(200, data={}))
    talk.mark_as_read("t1")
    assert b"lastReadMessage" not in rec.last.content


def test_mark_as_unread_uses_delete(make_talk):
    talk, rec = make_talk(ocs_response(200, data={}))
    talk.mark_as_unread("t1")
    assert rec.last.method == "DELETE"
    assert "/api/v1/chat/t1/read" in str(rec.last.url)


# --- conversation management ----------------------------------------------


def test_create_conversation_group(make_talk):
    talk, rec = make_talk(ocs_response(201, data={"token": "new", "displayName": "Team", "type": 2}))
    conv = talk.create_conversation(room_type=2, room_name="Team")
    assert conv == Conversation(token="new", name="Team", type=2)
    assert rec.last.method == "POST"
    assert b"roomType=2" in rec.last.content and b"roomName=Team" in rec.last.content


def test_create_conversation_invite(make_talk):
    talk, rec = make_talk(ocs_response(201, data={"token": "t", "displayName": "B", "type": 1}))
    talk.create_conversation(room_type=1, invite="bob")
    assert b"invite=bob" in rec.last.content


def test_rename_conversation_uses_put(make_talk):
    talk, rec = make_talk(ocs_response(200, data={}))
    talk.rename_conversation("t1", "New")
    assert rec.last.method == "PUT"
    assert str(rec.last.url).endswith("/api/v4/room/t1")
    assert b"roomName=New" in rec.last.content


def test_set_description_uses_put(make_talk):
    talk, rec = make_talk(ocs_response(200, data={}))
    talk.set_description("t1", "desc")
    assert "/api/v4/room/t1/description" in str(rec.last.url)
    assert b"description=desc" in rec.last.content


def test_delete_conversation_uses_delete(make_talk):
    talk, rec = make_talk(ocs_response(200, data={}))
    talk.delete_conversation("t1")
    assert rec.last.method == "DELETE"
    assert str(rec.last.url).endswith("/api/v4/room/t1")


# --- participant management -----------------------------------------------


def test_list_participants_returns_models(make_talk):
    talk, rec = make_talk(
        ocs_response(
            200,
            data=[{"attendeeId": 11, "actorId": "al", "displayName": "Al", "participantType": 1, "permissions": 254}],
        )
    )
    assert talk.list_participants("t1") == [
        Participant(attendee_id=11, actor_id="al", display_name="Al", participant_type=1, permissions=254)
    ]
    assert "/api/v4/room/t1/participants" in str(rec.last.url)


def test_add_participant_returns_type(make_talk):
    talk, rec = make_talk(ocs_response(200, data={"type": 3}))
    assert talk.add_participant("t1", "bob") == 3
    assert rec.last.method == "POST"
    assert b"newParticipant=bob" in rec.last.content and b"source=users" in rec.last.content


def test_add_participant_group_source(make_talk):
    talk, rec = make_talk(ocs_response(200, data={}))
    talk.add_participant("t1", "staff", source="groups")
    assert b"source=groups" in rec.last.content


def test_remove_participant_body(make_talk):
    talk, rec = make_talk(ocs_response(200, data={}))
    talk.remove_participant("t1", 11)
    assert rec.last.method == "DELETE"
    assert "/api/v4/room/t1/attendees" in str(rec.last.url)
    assert b"attendeeId=11" in rec.last.content


def test_set_participant_permissions(make_talk):
    talk, rec = make_talk(ocs_response(200, data={}))
    talk.set_participant_permissions("t1", 11, permissions=177, mode="set")
    assert rec.last.method == "PUT"
    assert "/api/v4/room/t1/attendees/permissions" in str(rec.last.url)
    assert b"attendeeId=11" in rec.last.content
    assert b"method=set" in rec.last.content
    assert b"permissions=177" in rec.last.content


# --- reactions ------------------------------------------------------------


def test_add_reaction_returns_by_emoji(make_talk):
    talk, rec = make_talk(ocs_response(201, data={"👍": [{"actorId": "al", "actorDisplayName": "Al", "timestamp": 9}]}))
    out = talk.add_reaction("t1", 42, "👍")
    assert out == {"👍": [Reaction(actor_id="al", actor_display_name="Al", timestamp=9)]}
    assert rec.last.method == "POST"
    assert "/api/v1/reaction/t1/42" in str(rec.last.url)


def test_remove_reaction_uses_delete(make_talk):
    talk, rec = make_talk(ocs_response(200, data={}))
    assert talk.remove_reaction("t1", 42, "👍") == {}
    assert rec.last.method == "DELETE"
    assert "/api/v1/reaction/t1/42" in str(rec.last.url)


def test_list_reactions_maps(make_talk):
    talk, rec = make_talk(ocs_response(200, data={"🎉": [{"actorId": "bo", "actorDisplayName": "Bo", "timestamp": 1}]}))
    assert talk.list_reactions("t1", 42) == {"🎉": [Reaction(actor_id="bo", actor_display_name="Bo", timestamp=1)]}
    assert rec.last.method == "GET"


def test_list_reactions_filter(make_talk):
    talk, rec = make_talk(ocs_response(200, data={"👍": []}))
    talk.list_reactions("t1", 42, reaction="👍")
    assert "reaction=" in str(rec.last.url)


# --- reminders ------------------------------------------------------------


def test_set_reminder_posts_timestamp(make_talk):
    talk, rec = make_talk(ocs_response(201, data={}))
    talk.set_reminder("t1", 42, 1893456000)
    assert rec.last.method == "POST"
    assert "/api/v1/chat/t1/42/reminder" in str(rec.last.url)
    assert b"timestamp=1893456000" in rec.last.content


def test_get_reminder_returns_timestamp(make_talk):
    talk, rec = make_talk(ocs_response(200, data={"timestamp": 1893456000}))
    assert talk.get_reminder("t1", 42) == 1893456000
    assert rec.last.method == "GET"


def test_delete_reminder_uses_delete(make_talk):
    talk, rec = make_talk(ocs_response(200, data={}))
    talk.delete_reminder("t1", 42)
    assert rec.last.method == "DELETE"
    assert "/api/v1/chat/t1/42/reminder" in str(rec.last.url)


# --- file sharing ---------------------------------------------------------


def test_share_file_uses_files_sharing(make_talk):
    talk, rec = make_talk(ocs_response(200, data={"id": 77}))
    assert talk.share_file("t1", "/Documents/r.pdf") == 77
    url = str(rec.last.url)
    assert "/ocs/v2.php/apps/files_sharing/api/v1/shares" in url
    assert "spreed" not in url
    body = rec.last.content.decode()
    assert "shareType=10" in body and "shareWith=t1" in body


def test_share_file_with_caption(make_talk):
    talk, rec = make_talk(ocs_response(200, data={"id": 78}))
    talk.share_file("t1", "/foo.txt", caption="hi")
    body = rec.last.content.decode()
    assert "talkMetaData" in body and "caption" in body
