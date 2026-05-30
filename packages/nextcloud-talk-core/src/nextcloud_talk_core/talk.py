"""High-level Nextcloud Talk client.

TalkClient wraps OCSClient and exposes one method per Talk operation, owning the
endpoint paths, payload shaping, and model mapping. It returns typed models
(see models.py) — no OCS/HTTP details leak to callers. This is the reusable
surface shared by the MCP server and the polling bridge.

API versions vary by domain (verified against
https://nextcloud-talk.readthedocs.io/en/latest/):
  - conversation + participant management: api/v4 (Nextcloud 22+)
  - chat, read-markers, reactions, reminders: api/v1
  - file sharing: the separate files_sharing OCS app
"""

from __future__ import annotations

import json

from nextcloud_talk_core.client import OCSClient
from nextcloud_talk_core.config import Settings
from nextcloud_talk_core.models import (
    Conversation,
    Mention,
    Message,
    Participant,
    Reaction,
)


def _reactions_by_emoji(data: dict | None) -> dict[str, list[Reaction]]:
    return {emoji: [Reaction.from_api(e) for e in entries] for emoji, entries in (data or {}).items()}


class TalkClient:
    """Domain-level client for the Nextcloud Talk (Spreed) API."""

    def __init__(self, settings: Settings, **client_kwargs) -> None:
        self._ocs = OCSClient(settings, **client_kwargs)

    @classmethod
    def from_env(cls, **client_kwargs) -> TalkClient:
        return cls(Settings.from_env(), **client_kwargs)

    def __enter__(self) -> TalkClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._ocs.close()

    # --- chat: read --------------------------------------------------------

    def list_conversations(self) -> list[Conversation]:
        data = self._ocs.get("/api/v4/room")
        return [Conversation.from_api(r) for r in data]

    def read_messages(self, token: str, limit: int = 30) -> list[Message]:
        data = self._ocs.get(
            f"/api/v1/chat/{token}",
            params={"lookIntoFuture": 0, "limit": limit},
        )
        return [Message.from_api(m) for m in data]

    def list_mentions(self, token: str, limit: int = 20) -> list[Mention]:
        data = self._ocs.get(
            f"/api/v1/chat/{token}/mentions",
            params={"search": "", "limit": limit},
        )
        return [Mention.from_api(m) for m in data]

    def wait_for_messages(
        self,
        token: str,
        last_known_message_id: int,
        limit: int = 100,
        timeout: int = 30,
    ) -> list[Message]:
        timeout = min(timeout, 60)
        limit = min(limit, 200)
        data = self._ocs.get(
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
        if not data:
            return []
        return [Message.from_api(m) for m in data]

    # --- chat: write -------------------------------------------------------

    def send_message(self, token: str, message: str, reply_to: int | None = None) -> Message:
        payload: dict = {"message": message}
        if reply_to is not None:
            payload["replyTo"] = reply_to
        data = self._ocs.post(f"/api/v1/chat/{token}", data=payload)
        return Message.from_api(data)

    def edit_message(self, token: str, message_id: int, message: str) -> Message:
        data = self._ocs.put(
            f"/api/v1/chat/{token}/{message_id}",
            data={"message": message},
        )
        return Message.from_api(data)

    def delete_message(self, token: str, message_id: int) -> str:
        """Delete a message. Returns the resulting system message text."""
        data = self._ocs.delete(f"/api/v1/chat/{token}/{message_id}")
        return (data or {}).get("systemMessage", "")

    # --- read-markers ------------------------------------------------------

    def mark_as_read(self, token: str, last_read_message: int | None = None) -> None:
        payload: dict = {}
        if last_read_message is not None:
            payload["lastReadMessage"] = last_read_message
        self._ocs.post(f"/api/v1/chat/{token}/read", data=payload)

    def mark_as_unread(self, token: str) -> None:
        self._ocs.delete(f"/api/v1/chat/{token}/read")

    # --- conversation management (api/v4) ----------------------------------

    def create_conversation(
        self,
        room_type: int,
        invite: str | None = None,
        room_name: str | None = None,
        source: str | None = None,
    ) -> Conversation:
        payload: dict = {"roomType": room_type}
        if invite is not None:
            payload["invite"] = invite
        if room_name is not None:
            payload["roomName"] = room_name
        if source is not None:
            payload["source"] = source
        data = self._ocs.post("/api/v4/room", data=payload)
        return Conversation.from_api(data)

    def rename_conversation(self, token: str, name: str) -> None:
        self._ocs.put(f"/api/v4/room/{token}", data={"roomName": name})

    def set_description(self, token: str, description: str) -> None:
        self._ocs.put(f"/api/v4/room/{token}/description", data={"description": description})

    def delete_conversation(self, token: str) -> None:
        self._ocs.delete(f"/api/v4/room/{token}")

    # --- participant management (api/v4) -----------------------------------

    def list_participants(self, token: str) -> list[Participant]:
        data = self._ocs.get(f"/api/v4/room/{token}/participants")
        return [Participant.from_api(p) for p in data]

    def add_participant(self, token: str, new_participant: str, source: str = "users") -> int | None:
        """Add a participant. Returns the new room type, if reported."""
        data = self._ocs.post(
            f"/api/v4/room/{token}/participants",
            data={"newParticipant": new_participant, "source": source},
        )
        return (data or {}).get("type")

    def remove_participant(self, token: str, attendee_id: int) -> None:
        self._ocs.delete(f"/api/v4/room/{token}/attendees", data={"attendeeId": attendee_id})

    def set_participant_permissions(
        self,
        token: str,
        attendee_id: int,
        permissions: int,
        mode: str = "set",
    ) -> None:
        """Set attendee permissions. `permissions` is the final bitmask
        (build it with permissions_from_flags). `mode`: set / add / remove."""
        self._ocs.put(
            f"/api/v4/room/{token}/attendees/permissions",
            data={"attendeeId": attendee_id, "method": mode, "permissions": permissions},
        )

    # --- reactions (api/v1) ------------------------------------------------

    def add_reaction(self, token: str, message_id: int, reaction: str) -> dict[str, list[Reaction]]:
        data = self._ocs.post(
            f"/api/v1/reaction/{token}/{message_id}",
            data={"reaction": reaction},
        )
        return _reactions_by_emoji(data)

    def remove_reaction(self, token: str, message_id: int, reaction: str) -> dict[str, list[Reaction]]:
        data = self._ocs.delete(
            f"/api/v1/reaction/{token}/{message_id}",
            data={"reaction": reaction},
        )
        return _reactions_by_emoji(data)

    def list_reactions(self, token: str, message_id: int, reaction: str | None = None) -> dict[str, list[Reaction]]:
        params = {"reaction": reaction} if reaction is not None else None
        data = self._ocs.get(f"/api/v1/reaction/{token}/{message_id}", params=params)
        return _reactions_by_emoji(data)

    # --- reminders (api/v1) ------------------------------------------------

    def set_reminder(self, token: str, message_id: int, timestamp: int) -> None:
        self._ocs.post(
            f"/api/v1/chat/{token}/{message_id}/reminder",
            data={"timestamp": timestamp},
        )

    def get_reminder(self, token: str, message_id: int) -> int | None:
        data = self._ocs.get(f"/api/v1/chat/{token}/{message_id}/reminder")
        return (data or {}).get("timestamp")

    def delete_reminder(self, token: str, message_id: int) -> None:
        self._ocs.delete(f"/api/v1/chat/{token}/{message_id}/reminder")

    # --- file attachments (files_sharing api/v1) ---------------------------

    def share_file(self, token: str, path: str, caption: str | None = None) -> str | int | None:
        """Share an existing Nextcloud file into a conversation. Returns the
        share id. `path` is the WebDAV path relative to the user root."""
        payload: dict = {"shareType": 10, "shareWith": token, "path": path}
        if caption is not None:
            payload["talkMetaData"] = json.dumps({"caption": caption})
        data = self._ocs.post("/api/v1/shares", data=payload, app="files_sharing")
        return (data or {}).get("id")
