"""Attendee permission bitmask helpers (Talk constants).

Bit 1 (Custom) is added by the server automatically whenever permissions != 0;
`permissions_from_flags` sets it explicitly for clarity.
"""

from __future__ import annotations

PERM_CUSTOM = 1
PERM_FLAGS = {
    "can_start_call": 2,
    "can_join_call": 4,
    "can_ignore_lobby": 8,
    "can_publish_audio": 16,
    "can_publish_video": 32,
    "can_publish_screen": 64,
    "can_post_chat": 128,
}


def permissions_from_flags(**flags: bool) -> int:
    """Combine named boolean capability flags into the Talk permission bitmask.

    Unknown flag names raise KeyError so typos surface early. The Custom bit (1)
    is OR-ed in whenever any flag is set.
    """
    permissions = sum(PERM_FLAGS[name] for name, on in flags.items() if on)
    if permissions:
        permissions |= PERM_CUSTOM
    return permissions
