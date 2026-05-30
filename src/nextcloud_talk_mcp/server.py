"""FastMCP server exposing Nextcloud Talk tools."""

from __future__ import annotations

from fastmcp import FastMCP

from nextcloud_talk_mcp.client import OCSClient
from nextcloud_talk_mcp.config import Settings

mcp = FastMCP("nextcloud-talk")

_client: OCSClient | None = None


def _get_client() -> OCSClient:
    if _client is None:
        raise RuntimeError("OCSClient not initialised — call main() before invoking tools")
    return _client


@mcp.tool()
def list_conversations() -> list[dict]:
    """List all Talk conversations (rooms) the user is part of.
    Returns token, name, type, unread, lastMessage for each.
    type: 1=one-to-one, 2=group, 3=public, 4=changelog."""
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


@mcp.tool()
def read_messages(token: str, limit: int = 30) -> list[dict]:
    """Read recent messages from a conversation.
    `token` comes from list_conversations. `limit` caps the message count."""
    data = _get_client().get(
        f"/api/v1/chat/{token}",
        params={"lookIntoFuture": 0, "limit": limit},
    )
    return [
        {
            "id": m["id"],
            "actor": m.get("actorDisplayName", m.get("actorId", "")),
            "timestamp": m["timestamp"],
            "message": m["message"],
        }
        for m in data
    ]


@mcp.tool()
def send_message(token: str, message: str, reply_to: int | None = None) -> dict:
    """Send a message to a conversation.
    `token` from list_conversations. `reply_to` optionally references a message id."""
    payload: dict = {"message": message}
    if reply_to is not None:
        payload["replyTo"] = reply_to
    data = _get_client().post(f"/api/v1/chat/{token}", data=payload)
    return {"id": data["id"], "sent": data["message"]}


@mcp.tool()
def list_mentions(token: str, limit: int = 20) -> list[dict]:
    """List users/rooms that can be mentioned in a conversation (for @-autocomplete)."""
    data = _get_client().get(
        f"/api/v1/chat/{token}/mentions",
        params={"search": "", "limit": limit},
    )
    return [{"id": m["id"], "label": m["label"], "source": m["source"]} for m in data]


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
