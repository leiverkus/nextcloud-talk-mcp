"""FastMCP server exposing Nextcloud Talk tools.

This is a thin wrapper over nextcloud_talk_core.TalkClient: each tool calls a
TalkClient method and serialises the typed model back to the established MCP
output dict/list. Endpoint paths, payload shaping, OCS parsing, and the
permission bitmask all live in the core — the server owns only the MCP surface
(tool names, docstrings, annotations, and the camelCase output schema).

Tools are annotated with MCP hints (readOnlyHint / destructiveHint) so clients
can warn before running write or destructive operations. These confirmations
are intentional and must not be bypassed.
"""

from __future__ import annotations

import sys
from dataclasses import asdict

from fastmcp import FastMCP
from nextcloud_talk_core import NextcloudConfigError, Reaction, TalkClient, permissions_from_flags

mcp = FastMCP("nextcloud-talk")

_talk: TalkClient | None = None


def _get_talk() -> TalkClient:
    if _talk is None:
        raise RuntimeError("TalkClient not initialised — call main() before invoking tools")
    return _talk


def _conversation_dict(c) -> dict:
    return {"token": c.token, "name": c.name, "type": c.type, "unread": c.unread, "lastMessage": c.last_message}


def _message_dict(m) -> dict:
    return {
        "id": m.id,
        "actor": m.actor,
        "timestamp": m.timestamp,
        "message": m.message,
        "attachments": [asdict(a) for a in m.attachments],
    }


def _reactions_dict(reactions: dict[str, list[Reaction]]) -> dict:
    return {emoji: [asdict(r) for r in entries] for emoji, entries in reactions.items()}


# --- chat: read ------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True})
def list_conversations() -> list[dict]:
    """List all Talk conversations (rooms) the user is part of.
    Returns token, name, type, unread, lastMessage for each.
    type: 1=one-to-one, 2=group, 3=public, 4=changelog, 6=note-to-self."""
    return [_conversation_dict(c) for c in _get_talk().list_conversations()]


@mcp.tool(annotations={"readOnlyHint": True})
def read_messages(token: str, limit: int = 30) -> list[dict]:
    """Read recent messages from a conversation.
    `token` comes from list_conversations. `limit` caps the message count."""
    return [_message_dict(m) for m in _get_talk().read_messages(token, limit)]


@mcp.tool(annotations={"readOnlyHint": True})
def list_mentions(token: str, limit: int = 20) -> list[dict]:
    """List users/rooms that can be mentioned in a conversation (for @-autocomplete)."""
    return [{"id": m.id, "label": m.label, "source": m.source} for m in _get_talk().list_mentions(token, limit)]


@mcp.tool(annotations={"readOnlyHint": True})
def wait_for_messages(
    token: str,
    last_known_message_id: int,
    limit: int = 100,
    timeout: int = 30,
) -> list[dict]:
    """Long-poll for NEW messages after `last_known_message_id`.

    Blocks server-side until a new message arrives or `timeout` seconds pass
    (then returns an empty list). Use the highest `id` from read_messages as
    `last_known_message_id`. `timeout` is capped at 60, `limit` at 200 by the
    API."""
    msgs = _get_talk().wait_for_messages(token, last_known_message_id, limit, timeout)
    return [_message_dict(m) for m in msgs]


# --- chat: write -----------------------------------------------------------


@mcp.tool()
def send_message(token: str, message: str, reply_to: int | None = None) -> dict:
    """Send a message to a conversation. WRITE operation.
    `token` from list_conversations. `reply_to` optionally references a message id."""
    m = _get_talk().send_message(token, message, reply_to)
    return {"id": m.id, "sent": m.message}


@mcp.tool()
def edit_message(token: str, message_id: int, message: str) -> dict:
    """Edit an existing chat message. WRITE operation.
    Requires the `edit-messages` capability and appropriate permissions."""
    m = _get_talk().edit_message(token, message_id, message)
    return {"id": m.id, "message": m.message}


@mcp.tool(annotations={"destructiveHint": True})
def delete_message(token: str, message_id: int) -> dict:
    """Delete a chat message. DESTRUCTIVE: removes the message for ALL
    participants. Requires the `delete-messages` capability. Cannot be undone."""
    system_message = _get_talk().delete_message(token, message_id)
    return {"id": message_id, "deleted": True, "systemMessage": system_message}


# --- read-markers ----------------------------------------------------------


@mcp.tool()
def mark_as_read(token: str, last_read_message: int | None = None) -> dict:
    """Mark a conversation as read. WRITE operation.
    `last_read_message` optionally pins the last-read message id; omit to mark
    everything read."""
    _get_talk().mark_as_read(token, last_read_message)
    return {"token": token, "read": True}


@mcp.tool()
def mark_as_unread(token: str) -> dict:
    """Mark a conversation as unread. WRITE operation."""
    _get_talk().mark_as_unread(token)
    return {"token": token, "unread": True}


# --- conversation management (api/v4) --------------------------------------


@mcp.tool()
def create_conversation(
    room_type: int,
    invite: str | None = None,
    room_name: str | None = None,
    source: str | None = None,
) -> dict:
    """Create a new conversation. WRITE operation.
    room_type: 1=one-to-one (set `invite` to a user id), 2=group, 3=public
    (set `room_name`). `source` defaults to users for the invite target."""
    c = _get_talk().create_conversation(room_type, invite, room_name, source)
    return {"token": c.token, "name": c.name, "type": c.type}


@mcp.tool()
def rename_conversation(token: str, name: str) -> dict:
    """Rename a conversation. WRITE operation. Name is capped at 255 chars."""
    _get_talk().rename_conversation(token, name)
    return {"token": token, "name": name}


@mcp.tool()
def set_description(token: str, description: str) -> dict:
    """Set a conversation's description. WRITE operation. Capped at 2000 chars."""
    _get_talk().set_description(token, description)
    return {"token": token, "description": description}


@mcp.tool(annotations={"destructiveHint": True})
def delete_conversation(token: str) -> dict:
    """Delete a conversation. DESTRUCTIVE: permanently removes the conversation
    and its history for ALL participants. Cannot be undone. Requires moderator
    or owner rights."""
    _get_talk().delete_conversation(token)
    return {"token": token, "deleted": True}


# --- participant management (api/v4) ---------------------------------------


@mcp.tool(annotations={"readOnlyHint": True})
def list_participants(token: str) -> list[dict]:
    """List participants of a conversation.
    Returns attendeeId (key for remove/permissions), actorId, displayName,
    participantType, permissions for each."""
    return [
        {
            "attendeeId": p.attendee_id,
            "actorId": p.actor_id,
            "displayName": p.display_name,
            "participantType": p.participant_type,
            "permissions": p.permissions,
        }
        for p in _get_talk().list_participants(token)
    ]


@mcp.tool()
def add_participant(token: str, new_participant: str, source: str = "users") -> dict:
    """Add a participant to a conversation. WRITE operation.
    `source`: users (default), groups, circles, emails, federated_users."""
    room_type = _get_talk().add_participant(token, new_participant, source)
    return {"token": token, "added": new_participant, "source": source, "type": room_type}


@mcp.tool(annotations={"destructiveHint": True})
def remove_participant(token: str, attendee_id: int) -> dict:
    """Remove a participant from a conversation. DESTRUCTIVE: removes the
    attendee's access. `attendee_id` comes from list_participants. Requires
    moderator rights."""
    _get_talk().remove_participant(token, attendee_id)
    return {"token": token, "removed_attendee": attendee_id}


@mcp.tool()
def set_participant_permissions(
    token: str,
    attendee_id: int,
    *,
    mode: str = "set",
    can_start_call: bool = False,
    can_join_call: bool = False,
    can_ignore_lobby: bool = False,
    can_publish_audio: bool = False,
    can_publish_video: bool = False,
    can_publish_screen: bool = False,
    can_post_chat: bool = False,
) -> dict:
    """Set a participant's permissions. WRITE operation.

    `attendee_id` comes from list_participants. `mode` is one of:
    set (replace), add (grant), remove (revoke). The boolean flags select
    capabilities; they are combined into the Talk permission bitmask. With
    mode=set, unselected flags are cleared."""
    permissions = permissions_from_flags(
        can_start_call=can_start_call,
        can_join_call=can_join_call,
        can_ignore_lobby=can_ignore_lobby,
        can_publish_audio=can_publish_audio,
        can_publish_video=can_publish_video,
        can_publish_screen=can_publish_screen,
        can_post_chat=can_post_chat,
    )
    _get_talk().set_participant_permissions(token, attendee_id, permissions, mode)
    return {"token": token, "attendeeId": attendee_id, "mode": mode, "permissions": permissions}


# --- reactions (api/v1, since Nextcloud 24) --------------------------------


@mcp.tool()
def add_reaction(token: str, message_id: int, reaction: str) -> dict:
    """Add an emoji reaction to a message. WRITE operation.
    `reaction` is a single emoji, e.g. "👍". Requires the `reactions` capability."""
    reactions = _get_talk().add_reaction(token, message_id, reaction)
    return {"messageId": message_id, "reaction": reaction, "reactions": _reactions_dict(reactions)}


@mcp.tool()
def remove_reaction(token: str, message_id: int, reaction: str) -> dict:
    """Remove your emoji reaction from a message. WRITE operation.
    `reaction` is the emoji to remove, e.g. "👍"."""
    reactions = _get_talk().remove_reaction(token, message_id, reaction)
    return {"messageId": message_id, "removed": reaction, "reactions": _reactions_dict(reactions)}


@mcp.tool(annotations={"readOnlyHint": True})
def list_reactions(token: str, message_id: int, reaction: str | None = None) -> dict:
    """List reactions on a message, keyed by emoji.
    `reaction` optionally filters to a single emoji."""
    return _reactions_dict(_get_talk().list_reactions(token, message_id, reaction))


# --- reminders (api/v1, capability remind-me-later) ------------------------


@mcp.tool()
def set_reminder(token: str, message_id: int, timestamp: int) -> dict:
    """Set a reminder on a message. WRITE operation.
    `timestamp` is the Unix time (seconds) when the reminder fires.
    Requires the `remind-me-later` capability."""
    _get_talk().set_reminder(token, message_id, timestamp)
    return {"messageId": message_id, "remindAt": timestamp}


@mcp.tool(annotations={"readOnlyHint": True})
def get_reminder(token: str, message_id: int) -> dict:
    """Get the reminder set on a message (if any)."""
    return {"messageId": message_id, "remindAt": _get_talk().get_reminder(token, message_id)}


@mcp.tool()
def delete_reminder(token: str, message_id: int) -> dict:
    """Delete the reminder on a message. WRITE operation."""
    _get_talk().delete_reminder(token, message_id)
    return {"messageId": message_id, "reminderCleared": True}


# --- file attachments (files_sharing api/v1) -------------------------------


@mcp.tool()
def share_file_to_conversation(token: str, path: str, caption: str | None = None) -> dict:
    """Share an EXISTING Nextcloud file into a conversation. WRITE operation.

    `path` is the file's WebDAV path relative to your user root, e.g.
    "/Documents/report.pdf". The file must already exist in your Nextcloud —
    this tool does NOT upload; it only shares. `caption` is an optional message
    shown with the attachment."""
    share_id = _get_talk().share_file(token, path, caption)
    return {"shareId": share_id, "token": token, "path": path}


def main() -> None:
    global _talk
    try:
        _talk = TalkClient.from_env()
    except NextcloudConfigError as exc:
        # Missing/invalid env vars: a clear message on stderr, not a traceback.
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    try:
        mcp.run()
    finally:
        _talk.close()
        _talk = None


if __name__ == "__main__":
    main()
