"""FastMCP server exposing Nextcloud Talk tools.

API versions vary by domain (verified against
https://nextcloud-talk.readthedocs.io/en/latest/):
  - conversation + participant management: api/v4 (since Nextcloud 22)
  - chat (messages, read-markers, long-poll): api/v1 (since Nextcloud 13)

Tools are annotated with MCP hints (readOnlyHint / destructiveHint) so clients
can warn before running write or destructive operations. These confirmations
are intentional and must not be bypassed.
"""

from __future__ import annotations

from fastmcp import FastMCP

from nextcloud_talk_mcp.client import OCSClient
from nextcloud_talk_mcp.config import Settings

mcp = FastMCP("nextcloud-talk")

_client: OCSClient | None = None

# Attendee permission bitmask flags (Talk constants). Bit 1 (Custom) is added
# automatically by the server whenever permissions != 0; we set it explicitly
# for clarity.
_PERM_CUSTOM = 1
_PERM_FLAGS = {
    "can_start_call": 2,
    "can_join_call": 4,
    "can_ignore_lobby": 8,
    "can_publish_audio": 16,
    "can_publish_video": 32,
    "can_publish_screen": 64,
    "can_post_chat": 128,
}


def _get_client() -> OCSClient:
    if _client is None:
        raise RuntimeError("OCSClient not initialised — call main() before invoking tools")
    return _client


def _format_message(m: dict) -> dict:
    """Shared message-shaping used by read_messages and wait_for_messages."""
    return {
        "id": m["id"],
        "actor": m.get("actorDisplayName", m.get("actorId", "")),
        "timestamp": m["timestamp"],
        "message": m["message"],
    }


# --- chat: read ------------------------------------------------------------


@mcp.tool(annotations={"readOnlyHint": True})
def list_conversations() -> list[dict]:
    """List all Talk conversations (rooms) the user is part of.
    Returns token, name, type, unread, lastMessage for each.
    type: 1=one-to-one, 2=group, 3=public, 4=changelog, 6=note-to-self."""
    data = _get_client().get("/api/v4/room")
    return [
        {
            "token": r["token"],
            "name": r["displayName"],
            "type": r["type"],
            "unread": r.get("unreadMessages", 0),
            "lastMessage": (r.get("lastMessage") or {}).get("message", ""),
        }
        for r in data
    ]


@mcp.tool(annotations={"readOnlyHint": True})
def read_messages(token: str, limit: int = 30) -> list[dict]:
    """Read recent messages from a conversation.
    `token` comes from list_conversations. `limit` caps the message count."""
    data = _get_client().get(
        f"/api/v1/chat/{token}",
        params={"lookIntoFuture": 0, "limit": limit},
    )
    return [_format_message(m) for m in data]


@mcp.tool(annotations={"readOnlyHint": True})
def list_mentions(token: str, limit: int = 20) -> list[dict]:
    """List users/rooms that can be mentioned in a conversation (for @-autocomplete)."""
    data = _get_client().get(
        f"/api/v1/chat/{token}/mentions",
        params={"search": "", "limit": limit},
    )
    return [{"id": m["id"], "label": m["label"], "source": m["source"]} for m in data]


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
    timeout = min(timeout, 60)
    limit = min(limit, 200)
    data = _get_client().get(
        f"/api/v1/chat/{token}",
        params={
            "lookIntoFuture": 1,
            "lastKnownMessageId": last_known_message_id,
            "limit": limit,
            "timeout": timeout,
        },
        # HTTP timeout must outlast the server-side long-poll timeout.
        timeout=timeout + 30,
    )
    if not data:  # 304 / empty long-poll returns no data
        return []
    return [_format_message(m) for m in data]


# --- chat: write -----------------------------------------------------------


@mcp.tool()
def send_message(token: str, message: str, reply_to: int | None = None) -> dict:
    """Send a message to a conversation. WRITE operation.
    `token` from list_conversations. `reply_to` optionally references a message id."""
    payload: dict = {"message": message}
    if reply_to is not None:
        payload["replyTo"] = reply_to
    data = _get_client().post(f"/api/v1/chat/{token}", data=payload)
    return {"id": data["id"], "sent": data["message"]}


@mcp.tool()
def edit_message(token: str, message_id: int, message: str) -> dict:
    """Edit an existing chat message. WRITE operation.
    Requires the `edit-messages` capability and appropriate permissions."""
    data = _get_client().put(
        f"/api/v1/chat/{token}/{message_id}",
        data={"message": message},
    )
    return {"id": data["id"], "message": data["message"]}


@mcp.tool(annotations={"destructiveHint": True})
def delete_message(token: str, message_id: int) -> dict:
    """Delete a chat message. DESTRUCTIVE: removes the message for ALL
    participants. Requires the `delete-messages` capability. Cannot be undone."""
    data = _get_client().delete(f"/api/v1/chat/{token}/{message_id}")
    return {"id": message_id, "deleted": True, "systemMessage": (data or {}).get("systemMessage", "")}


# --- read-markers ----------------------------------------------------------


@mcp.tool()
def mark_as_read(token: str, last_read_message: int | None = None) -> dict:
    """Mark a conversation as read. WRITE operation.
    `last_read_message` optionally pins the last-read message id; omit to mark
    everything read."""
    payload: dict = {}
    if last_read_message is not None:
        payload["lastReadMessage"] = last_read_message
    _get_client().post(f"/api/v1/chat/{token}/read", data=payload)
    return {"token": token, "read": True}


@mcp.tool()
def mark_as_unread(token: str) -> dict:
    """Mark a conversation as unread. WRITE operation."""
    _get_client().delete(f"/api/v1/chat/{token}/read")
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
    payload: dict = {"roomType": room_type}
    if invite is not None:
        payload["invite"] = invite
    if room_name is not None:
        payload["roomName"] = room_name
    if source is not None:
        payload["source"] = source
    data = _get_client().post("/api/v4/room", data=payload)
    return {"token": data["token"], "name": data["displayName"], "type": data["type"]}


@mcp.tool()
def rename_conversation(token: str, name: str) -> dict:
    """Rename a conversation. WRITE operation. Name is capped at 255 chars."""
    _get_client().put(f"/api/v4/room/{token}", data={"roomName": name})
    return {"token": token, "name": name}


@mcp.tool()
def set_description(token: str, description: str) -> dict:
    """Set a conversation's description. WRITE operation. Capped at 2000 chars."""
    _get_client().put(f"/api/v4/room/{token}/description", data={"description": description})
    return {"token": token, "description": description}


@mcp.tool(annotations={"destructiveHint": True})
def delete_conversation(token: str) -> dict:
    """Delete a conversation. DESTRUCTIVE: permanently removes the conversation
    and its history for ALL participants. Cannot be undone. Requires moderator
    or owner rights."""
    _get_client().delete(f"/api/v4/room/{token}")
    return {"token": token, "deleted": True}


# --- participant management (api/v4) ---------------------------------------


@mcp.tool(annotations={"readOnlyHint": True})
def list_participants(token: str) -> list[dict]:
    """List participants of a conversation.
    Returns attendeeId (key for remove/permissions), actorId, displayName,
    participantType, permissions for each."""
    data = _get_client().get(f"/api/v4/room/{token}/participants")
    return [
        {
            "attendeeId": p.get("attendeeId"),
            "actorId": p.get("actorId", ""),
            "displayName": p.get("displayName", ""),
            "participantType": p.get("participantType"),
            "permissions": p.get("permissions"),
        }
        for p in data
    ]


@mcp.tool()
def add_participant(token: str, new_participant: str, source: str = "users") -> dict:
    """Add a participant to a conversation. WRITE operation.
    `source`: users (default), groups, circles, emails, federated_users."""
    data = _get_client().post(
        f"/api/v4/room/{token}/participants",
        data={"newParticipant": new_participant, "source": source},
    )
    return {"token": token, "added": new_participant, "source": source, "type": (data or {}).get("type")}


@mcp.tool(annotations={"destructiveHint": True})
def remove_participant(token: str, attendee_id: int) -> dict:
    """Remove a participant from a conversation. DESTRUCTIVE: removes the
    attendee's access. `attendee_id` comes from list_participants. Requires
    moderator rights."""
    _get_client().delete(f"/api/v4/room/{token}/attendees", data={"attendeeId": attendee_id})
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
    flags = {
        "can_start_call": can_start_call,
        "can_join_call": can_join_call,
        "can_ignore_lobby": can_ignore_lobby,
        "can_publish_audio": can_publish_audio,
        "can_publish_video": can_publish_video,
        "can_publish_screen": can_publish_screen,
        "can_post_chat": can_post_chat,
    }
    permissions = sum(_PERM_FLAGS[name] for name, on in flags.items() if on)
    if permissions:
        permissions |= _PERM_CUSTOM
    _get_client().put(
        f"/api/v4/room/{token}/attendees/permissions",
        data={"attendeeId": attendee_id, "method": mode, "permissions": permissions},
    )
    return {"token": token, "attendeeId": attendee_id, "mode": mode, "permissions": permissions}


def main() -> None:
    global _client
    settings = Settings.from_env()
    _client = OCSClient(settings)
    try:
        mcp.run()
    finally:
        _client.close()
        _client = None


if __name__ == "__main__":
    main()
