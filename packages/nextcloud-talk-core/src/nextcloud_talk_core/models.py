"""Typed data models for the Nextcloud Talk API.

These dataclasses are the public, SemVer-stable contract of the core: the
`from_api` classmethods encapsulate the defensive parsing of OCS payloads, so
the field shape is the single source of truth shared by every consumer
(MCP server, polling bridge, …). Field names are snake_case.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Attachment:
    """A file shared into a conversation (a `file` rich-object)."""

    name: str | None = None
    path: str | None = None
    mimetype: str | None = None
    size: str | None = None
    id: str | None = None
    link: str | None = None

    _FIELDS = ("name", "path", "mimetype", "size", "id", "link")

    @classmethod
    def from_param(cls, param: dict[str, Any]) -> Attachment:
        return cls(**{key: param.get(key) for key in cls._FIELDS})


@dataclass
class Message:
    id: int
    actor: str
    timestamp: int
    message: str
    attachments: list[Attachment] = field(default_factory=list)

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Message:
        attachments = [
            Attachment.from_param(param)
            for param in (raw.get("messageParameters") or {}).values()
            if isinstance(param, dict) and param.get("type") == "file"
        ]
        return cls(
            id=raw["id"],
            actor=raw.get("actorDisplayName", raw.get("actorId", "")),
            timestamp=raw["timestamp"],
            message=raw["message"],
            attachments=attachments,
        )


@dataclass
class Conversation:
    token: str
    name: str
    type: int
    unread: int = 0
    last_message: str = ""

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Conversation:
        return cls(
            token=raw["token"],
            name=raw["displayName"],
            type=raw["type"],
            unread=raw.get("unreadMessages", 0),
            last_message=(raw.get("lastMessage") or {}).get("message", ""),
        )


@dataclass
class Participant:
    attendee_id: int | None
    actor_id: str
    display_name: str
    participant_type: int | None
    permissions: int | None

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Participant:
        return cls(
            attendee_id=raw.get("attendeeId"),
            actor_id=raw.get("actorId", ""),
            display_name=raw.get("displayName", ""),
            participant_type=raw.get("participantType"),
            permissions=raw.get("permissions"),
        )


@dataclass
class Mention:
    id: str
    label: str
    source: str

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Mention:
        return cls(id=raw["id"], label=raw["label"], source=raw["source"])


@dataclass
class Reaction:
    actor_id: str
    actor_display_name: str
    timestamp: int | None

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Reaction:
        return cls(
            actor_id=raw.get("actorId", ""),
            actor_display_name=raw.get("actorDisplayName", ""),
            timestamp=raw.get("timestamp"),
        )
