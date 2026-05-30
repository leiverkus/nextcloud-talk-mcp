#!/usr/bin/env python3
"""Manual live smoke test against a real Nextcloud Talk instance.

NOT part of the test suite — this makes real network calls and is meant to be
run by hand once, to confirm the package works end-to-end against the actual
instance. Throwaway helper; safe to delete before committing.

Run it from this subdirectory location (NOT the repo root) so the leftover
prototype `nextcloud_talk_mcp.py` in the repo root does not shadow the
installed package:

    source .venv/bin/activate
    export NC_URL="https://cloud.uni-oldenburg.de"
    export NC_USER="your-username"
    export NC_APP_PASSWORD="xxxxx-xxxxx-xxxxx-xxxxx"   # app password, NOT login pw
    python scripts/smoke_live.py
"""

from __future__ import annotations

import sys

import nextcloud_talk_mcp.server as server
from nextcloud_talk_mcp.client import OCSClient
from nextcloud_talk_mcp.config import Settings
from nextcloud_talk_mcp.errors import (
    NextcloudAuthError,
    NextcloudConfigError,
    NextcloudNotFoundError,
)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    try:
        settings = Settings.from_env()
    except NextcloudConfigError as exc:
        print(f"[config] {exc}")
        return 2

    print(f"Target: {settings.nc_url}  (user: {settings.nc_user})")
    server._client = OCSClient(settings)

    # 1. list_conversations
    section("list_conversations()")
    rooms = server.list_conversations()
    print(f"{len(rooms)} room(s)")
    for r in rooms[:10]:
        print(f"  - [{r['type']}] {r['name']!r:40} token={r['token']:8} unread={r['unread']}")
    if not rooms:
        print("  (no rooms — cannot continue message checks)")
        return 0

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

    section("DONE — all live checks ran")
    return 0


if __name__ == "__main__":
    sys.exit(main())
