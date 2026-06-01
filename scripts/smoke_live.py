#!/usr/bin/env python3
"""Manual live smoke test against a real Nextcloud Talk instance.

NOT part of the test suite — this makes real network calls and is meant to be
run by hand to confirm the package works end-to-end against the actual instance.

Run it from the repo root (the module resolves from the installed package):

    source .venv/bin/activate
    export NC_URL="https://cloud.example.com"
    export NC_USER="your-username"
    export NC_APP_PASSWORD="xxxxx-xxxxx-xxxxx-xxxxx"   # app password, NOT login pw
    python scripts/smoke_live.py              # read-only checks (safe)
    python scripts/smoke_live.py --lifecycle  # also exercise write/new tools
    python scripts/smoke_live.py --share-file /Documents/test.pdf  # + share & read back a file

The default run is read-only: it lists conversations, reads messages, resolves
mentions, and checks the two error paths. It changes nothing.

With --lifecycle it additionally creates a THROWAWAY group conversation, runs
the write and management tools (rename, set_description, participants,
read-markers, long-poll, edit/delete message) against THAT room only, and
deletes it again at the end. Destructive tools are never pointed at your real
conversations.
"""

from __future__ import annotations

import sys

import nextcloud_talk_mcp.server as server
from nextcloud_talk_core import (
    NextcloudAuthError,
    NextcloudConfigError,
    NextcloudNotFoundError,
    OCSClient,
    Settings,
    TalkClient,
)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def read_only_checks(settings: Settings) -> None:
    # 1. list_conversations
    section("list_conversations()")
    rooms = server.list_conversations()
    print(f"{len(rooms)} room(s)")
    for r in rooms[:10]:
        print(
            f"  - [{r['type']}] {r['name']!r:40} token={r['token']:8} unread={r['unread']}"
        )
    if not rooms:
        print("  (no rooms — skipping message checks)")
    else:
        token = rooms[0]["token"]

        # 2. read_messages
        section(f"read_messages({token!r}, limit=5)")
        msgs = server.read_messages(token, limit=5)
        print(f"{len(msgs)} message(s)")
        for m in msgs[-5:]:
            text = (m["message"] or "").replace("\n", " ")[:60]
            print(f"  - #{m['id']} {m['actor']!r}: {text!r}")

        # 3. list_mentions
        section(f"list_mentions({token!r}, limit=5)")
        try:
            mentions = server.list_mentions(token, limit=5)
            print(f"{len(mentions)} candidate(s)")
            for mn in mentions[:5]:
                print(f"  - {mn['source']}/{mn['id']}: {mn['label']!r}")
        except Exception as exc:  # noqa: BLE001 — mentions can 4xx on some room types
            print(f"  (skipped: {type(exc).__name__}: {exc})")

    # 4. Error path: bogus token → NextcloudNotFoundError
    section("read_messages('definitely-not-a-real-token') → expect NotFound")
    try:
        server.read_messages("definitely-not-a-real-token", limit=1)
        print("  UNEXPECTED: no error raised")
    except NextcloudNotFoundError as exc:
        print(f"  OK NextcloudNotFoundError: {exc}")
    except NextcloudAuthError as exc:
        print(f"  (instance returned auth error instead: {exc})")

    # 5. Error path: wrong app password → NextcloudAuthError
    section("wrong app password → expect Auth error")
    bad = Settings(settings.nc_url, settings.nc_user, "wrong-password-xxxxx")
    bad_client = OCSClient(bad)
    try:
        bad_client.get("/api/v4/room")
        print("  UNEXPECTED: no error raised")
    except NextcloudAuthError as exc:
        print(f"  OK NextcloudAuthError: {exc}")
    finally:
        bad_client.close()


def lifecycle_checks(share_file: str | None = None) -> None:
    """Create a throwaway room, exercise the new tools, then delete it.

    If `share_file` is given (a WebDAV path), also share that existing file
    into the room and read it back to verify attachment parsing."""
    section("create_conversation(room_type=2, room_name='MCP smoke test')")
    room = server.create_conversation(room_type=2, room_name="MCP smoke test")
    token = room["token"]
    print(f"  created token={token} name={room['name']!r} type={room['type']}")

    try:
        section(f"rename_conversation({token!r}, 'MCP smoke test (renamed)')")
        print(f"  {server.rename_conversation(token, 'MCP smoke test (renamed)')}")

        section(f"set_description({token!r}, ...)")
        print(
            f"  {server.set_description(token, 'Created by scripts/smoke_live.py — safe to delete.')}"
        )

        section(f"list_participants({token!r})")
        parts = server.list_participants(token)
        for p in parts:
            print(
                f"  - attendeeId={p['attendeeId']} {p['actorId']!r} type={p['participantType']} perms={p['permissions']}"
            )

        section(f"send_message({token!r}, 'hello from smoke test')")
        sent = server.send_message(token, "hello from smoke test")
        msg_id = sent["id"]
        print(f"  sent id={msg_id}")

        section(f"edit_message({token!r}, {msg_id}, 'edited by smoke test')")
        print(f"  {server.edit_message(token, msg_id, 'edited by smoke test')}")

        section(f"add_reaction({token!r}, {msg_id}, '👍')")
        print(f"  {server.add_reaction(token, msg_id, '👍')}")

        section(f"list_reactions({token!r}, {msg_id})")
        print(f"  {server.list_reactions(token, msg_id)}")

        section(f"remove_reaction({token!r}, {msg_id}, '👍')")
        print(f"  {server.remove_reaction(token, msg_id, '👍')}")

        section(f"set_reminder({token!r}, {msg_id})")
        # A fixed far-future timestamp (2030-01-01) — the value is irrelevant for
        # the smoke test, which deletes the reminder again immediately.
        remind_at = 1893456000
        try:
            print(f"  {server.set_reminder(token, msg_id, remind_at)}")
            section(f"get_reminder({token!r}, {msg_id})")
            print(f"  {server.get_reminder(token, msg_id)}")
            section(f"delete_reminder({token!r}, {msg_id})")
            print(f"  {server.delete_reminder(token, msg_id)}")
        except Exception as exc:  # noqa: BLE001 — remind-me-later capability may be off
            print(f"  (skipped reminders: {type(exc).__name__}: {exc})")

        section(f"mark_as_read({token!r}, last_read_message={msg_id})")
        print(f"  {server.mark_as_read(token, last_read_message=msg_id)}")

        section(f"mark_as_unread({token!r})")
        print(f"  {server.mark_as_unread(token)}")

        section(
            f"wait_for_messages({token!r}, last_known_message_id={msg_id}, timeout=3)"
        )
        new = server.wait_for_messages(token, last_known_message_id=msg_id, timeout=3)
        print(f"  returned {len(new)} message(s) after long-poll")

        section(f"delete_message({token!r}, {msg_id})  [destructive, own message]")
        print(f"  {server.delete_message(token, msg_id)}")

        if share_file is not None:
            section(f"share_file_to_conversation({token!r}, {share_file!r})")
            shared = server.share_file_to_conversation(
                token, share_file, caption="smoke test attachment"
            )
            print(f"  {shared}")

            section(f"read_messages({token!r}) → verify attachments parsed")
            found = False
            for m in server.read_messages(token, limit=10):
                if m["attachments"]:
                    found = True
                    print(f"  #{m['id']} attachments: {m['attachments']}")
            if not found:
                print("  WARNING: no message with a parsed attachment found")
    finally:
        # Always clean up the throwaway room, even if a step above failed.
        section(f"delete_conversation({token!r})  [cleanup of throwaway room]")
        try:
            print(f"  {server.delete_conversation(token)}")
        except Exception as exc:  # noqa: BLE001
            print(f"  WARNING: cleanup failed, delete room {token!r} manually: {exc}")


def _parse_share_file(argv: list[str]) -> str | None:
    """Extract the value of --share-file PATH (implies --lifecycle)."""
    for i, arg in enumerate(argv):
        if arg == "--share-file" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--share-file="):
            return arg.split("=", 1)[1]
    return None


def main() -> int:
    argv = sys.argv[1:]
    share_file = _parse_share_file(argv)
    # --share-file implies the lifecycle run (it shares into the throwaway room).
    lifecycle = "--lifecycle" in argv or share_file is not None

    try:
        settings = Settings.from_env()
    except NextcloudConfigError as exc:
        print(f"[config] {exc}")
        return 2

    print(f"Target: {settings.nc_url}  (user: {settings.nc_user})")
    print(
        f"Mode: {'lifecycle (creates + deletes a throwaway room)' if lifecycle else 'read-only'}"
    )
    if share_file is not None:
        print(f"Share file: {share_file}")
    server._talk = TalkClient(settings)

    read_only_checks(settings)
    if lifecycle:
        lifecycle_checks(share_file=share_file)

    section("DONE — all live checks ran")
    return 0


if __name__ == "__main__":
    sys.exit(main())
