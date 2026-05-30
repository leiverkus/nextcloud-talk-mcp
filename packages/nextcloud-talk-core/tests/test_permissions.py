"""Tests for the attendee permission bitmask helper."""

from __future__ import annotations

import pytest

from nextcloud_talk_core.permissions import permissions_from_flags


def test_no_flags_is_zero():
    assert permissions_from_flags() == 0


def test_single_flag_adds_custom_bit():
    # can_publish_audio (16) | custom (1) = 17
    assert permissions_from_flags(can_publish_audio=True) == 17


def test_combined_flags():
    # audio (16) | video (32) | chat (128) = 176, + custom (1) = 177
    assert permissions_from_flags(can_publish_audio=True, can_publish_video=True, can_post_chat=True) == 177


def test_false_flags_ignored():
    assert permissions_from_flags(can_start_call=False, can_join_call=True) == 4 | 1


def test_unknown_flag_raises():
    with pytest.raises(KeyError):
        permissions_from_flags(can_teleport=True)
