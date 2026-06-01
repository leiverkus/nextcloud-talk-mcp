"""Tests for the MCP tool wrappers.

The server is a thin layer over TalkClient (endpoint/OCS logic is tested in the
core package). These tests install a MagicMock as the module-global `_talk`,
stub it to return core models, and assert that each tool (a) calls the right
TalkClient method with the right args and (b) serialises the result to the
established MCP output dict.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from nextcloud_talk_core import (
    Attachment,
    Conversation,
    Mention,
    Message,
    Participant,
    Reaction,
)

import nextcloud_talk_mcp.server as server


@pytest.fixture
def talk():
    """Install a MagicMock TalkClient as server._talk; restore after."""
    previous = server._talk
    mock = MagicMock()
    server._talk = mock
    yield mock
    server._talk = previous


# --- chat: read -----------------------------------------------------------


def test_list_conversations_serialises(talk):
    talk.list_conversations.return_value = [
        Conversation(token="t1", name="Team", type=2, unread=5, last_message="hello")
    ]
    assert server.list_conversations() == [
        {"token": "t1", "name": "Team", "type": 2, "unread": 5, "lastMessage": "hello"}
    ]
    talk.list_conversations.assert_called_once_with()


def test_read_messages_serialises_with_attachments(talk):
    talk.read_messages.return_value = [
        Message(id=1, actor="Alice", timestamp=1000, message="hi", attachments=[Attachment(name="x.pdf")])
    ]
    result = server.read_messages("t1", limit=5)
    assert result == [
        {
            "id": 1,
            "actor": "Alice",
            "timestamp": 1000,
            "message": "hi",
            "attachments": [{"name": "x.pdf", "path": None, "mimetype": None, "size": None, "id": None, "link": None}],
        }
    ]
    talk.read_messages.assert_called_once_with("t1", 5)


def test_read_messages_empty_attachments(talk):
    talk.read_messages.return_value = [Message(id=2, actor="A", timestamp=1, message="x")]
    assert server.read_messages("t1")[0]["attachments"] == []


def test_list_mentions_serialises(talk):
    talk.list_mentions.return_value = [Mention(id="bob", label="Bob", source="users")]
    assert server.list_mentions("t1", limit=10) == [{"id": "bob", "label": "Bob", "source": "users"}]
    talk.list_mentions.assert_called_once_with("t1", 10)


def test_wait_for_messages_passes_args(talk):
    talk.wait_for_messages.return_value = [Message(id=7, actor="A", timestamp=9, message="n")]
    result = server.wait_for_messages("t1", last_known_message_id=5, limit=50, timeout=10)
    assert result[0]["id"] == 7
    talk.wait_for_messages.assert_called_once_with("t1", 5, 50, 10)


# --- chat: write ----------------------------------------------------------


def test_send_message(talk):
    talk.send_message.return_value = Message(id=99, actor="A", timestamp=1, message="sent text")
    assert server.send_message("t1", "sent text") == {"id": 99, "sent": "sent text"}
    talk.send_message.assert_called_once_with("t1", "sent text", None)


def test_send_message_reply_to(talk):
    talk.send_message.return_value = Message(id=5, actor="A", timestamp=1, message="re")
    server.send_message("t1", "re", reply_to=42)
    talk.send_message.assert_called_once_with("t1", "re", 42)


def test_edit_message(talk):
    talk.edit_message.return_value = Message(id=42, actor="A", timestamp=1, message="edited")
    assert server.edit_message("t1", 42, "edited") == {"id": 42, "message": "edited"}
    talk.edit_message.assert_called_once_with("t1", 42, "edited")


def test_delete_message(talk):
    talk.delete_message.return_value = "message_deleted"
    assert server.delete_message("t1", 42) == {"id": 42, "deleted": True, "systemMessage": "message_deleted"}
    talk.delete_message.assert_called_once_with("t1", 42)


# --- read-markers ---------------------------------------------------------


def test_mark_as_read(talk):
    assert server.mark_as_read("t1", last_read_message=99) == {"token": "t1", "read": True}
    talk.mark_as_read.assert_called_once_with("t1", 99)


def test_mark_as_unread(talk):
    assert server.mark_as_unread("t1") == {"token": "t1", "unread": True}
    talk.mark_as_unread.assert_called_once_with("t1")


# --- conversation management ----------------------------------------------


def test_create_conversation(talk):
    talk.create_conversation.return_value = Conversation(token="new", name="Team", type=2)
    assert server.create_conversation(room_type=2, room_name="Team") == {"token": "new", "name": "Team", "type": 2}
    talk.create_conversation.assert_called_once_with(2, None, "Team", None)


def test_rename_conversation(talk):
    assert server.rename_conversation("t1", "New") == {"token": "t1", "name": "New"}
    talk.rename_conversation.assert_called_once_with("t1", "New")


def test_set_description(talk):
    assert server.set_description("t1", "desc") == {"token": "t1", "description": "desc"}
    talk.set_description.assert_called_once_with("t1", "desc")


def test_delete_conversation(talk):
    assert server.delete_conversation("t1") == {"token": "t1", "deleted": True}
    talk.delete_conversation.assert_called_once_with("t1")


# --- participant management -----------------------------------------------


def test_list_participants_serialises(talk):
    talk.list_participants.return_value = [
        Participant(attendee_id=11, actor_id="al", display_name="Al", participant_type=1, permissions=254)
    ]
    assert server.list_participants("t1") == [
        {"attendeeId": 11, "actorId": "al", "displayName": "Al", "participantType": 1, "permissions": 254}
    ]


def test_add_participant(talk):
    talk.add_participant.return_value = 3
    assert server.add_participant("t1", "bob") == {
        "token": "t1",
        "added": "bob",
        "source": "users",
        "type": 3,
    }
    talk.add_participant.assert_called_once_with("t1", "bob", "users")


def test_remove_participant(talk):
    assert server.remove_participant("t1", 11) == {"token": "t1", "removed_attendee": 11}
    talk.remove_participant.assert_called_once_with("t1", 11)


def test_set_participant_permissions_builds_bitmask(talk):
    result = server.set_participant_permissions(
        "t1", 11, can_publish_audio=True, can_publish_video=True, can_post_chat=True
    )
    # 16 | 32 | 128 = 176, + custom 1 = 177
    assert result == {"token": "t1", "attendeeId": 11, "mode": "set", "permissions": 177}
    talk.set_participant_permissions.assert_called_once_with("t1", 11, 177, "set")


def test_set_participant_permissions_no_flags(talk):
    result = server.set_participant_permissions("t1", 11, mode="remove")
    assert result["permissions"] == 0
    talk.set_participant_permissions.assert_called_once_with("t1", 11, 0, "remove")


# --- reactions ------------------------------------------------------------


def test_add_reaction_serialises(talk):
    talk.add_reaction.return_value = {"👍": [Reaction(actor_id="al", actor_display_name="Al", timestamp=9)]}
    result = server.add_reaction("t1", 42, "👍")
    assert result == {
        "messageId": 42,
        "reaction": "👍",
        "reactions": {"👍": [{"actor_id": "al", "actor_display_name": "Al", "timestamp": 9}]},
    }
    talk.add_reaction.assert_called_once_with("t1", 42, "👍")


def test_remove_reaction(talk):
    talk.remove_reaction.return_value = {}
    assert server.remove_reaction("t1", 42, "👍") == {"messageId": 42, "removed": "👍", "reactions": {}}
    talk.remove_reaction.assert_called_once_with("t1", 42, "👍")


def test_list_reactions(talk):
    talk.list_reactions.return_value = {"🎉": [Reaction(actor_id="bo", actor_display_name="Bo", timestamp=1)]}
    assert server.list_reactions("t1", 42) == {"🎉": [{"actor_id": "bo", "actor_display_name": "Bo", "timestamp": 1}]}
    talk.list_reactions.assert_called_once_with("t1", 42, None)


# --- reminders ------------------------------------------------------------


def test_set_reminder(talk):
    assert server.set_reminder("t1", 42, 1893456000) == {"messageId": 42, "remindAt": 1893456000}
    talk.set_reminder.assert_called_once_with("t1", 42, 1893456000)


def test_get_reminder(talk):
    talk.get_reminder.return_value = 1893456000
    assert server.get_reminder("t1", 42) == {"messageId": 42, "remindAt": 1893456000}
    talk.get_reminder.assert_called_once_with("t1", 42)


def test_delete_reminder(talk):
    assert server.delete_reminder("t1", 42) == {"messageId": 42, "reminderCleared": True}
    talk.delete_reminder.assert_called_once_with("t1", 42)


# --- file sharing ---------------------------------------------------------


def test_share_file(talk):
    talk.share_file.return_value = 77
    assert server.share_file_to_conversation("t1", "/Documents/r.pdf") == {
        "shareId": 77,
        "token": "t1",
        "path": "/Documents/r.pdf",
    }
    talk.share_file.assert_called_once_with("t1", "/Documents/r.pdf", None)


def test_share_file_with_caption(talk):
    talk.share_file.return_value = 78
    server.share_file_to_conversation("t1", "/foo.txt", caption="hi")
    talk.share_file.assert_called_once_with("t1", "/foo.txt", "hi")


# --- guard ----------------------------------------------------------------


def test_tool_without_client_raises(monkeypatch):
    monkeypatch.setattr(server, "_talk", None)
    with pytest.raises(RuntimeError, match="not initialised"):
        server.list_conversations()


def test_main_config_error_exits_cleanly(monkeypatch, capsys):
    from nextcloud_talk_core import NextcloudConfigError

    def boom():
        raise NextcloudConfigError("NC_URL is not set.")

    monkeypatch.setattr(server.TalkClient, "from_env", staticmethod(boom))
    with pytest.raises(SystemExit) as exc:
        server.main()
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "Configuration error" in err
    assert "NC_URL is not set" in err
