"""nextcloud-talk-core — reusable, MCP-free OCS client for Nextcloud Talk.

Public API (SemVer-stable contract):
  - TalkClient        — high-level domain methods returning typed models
  - OCSClient         — low-level OCS HTTP client
  - Settings          — env-var configuration
  - models            — Conversation, Message, Attachment, Participant, Mention, Reaction
  - errors            — exception hierarchy
  - permissions_from_flags — build the attendee permission bitmask
"""

# __version__ must be defined before importing submodules that read it
# (client.py uses it for the User-Agent header).
__version__ = "1.0.2"

from nextcloud_talk_core.client import OCSClient
from nextcloud_talk_core.config import Settings
from nextcloud_talk_core.errors import (
    NextcloudAuthError,
    NextcloudConfigError,
    NextcloudNotFoundError,
    NextcloudOCSError,
    NextcloudTalkError,
    NextcloudTransportError,
)
from nextcloud_talk_core.models import (
    Attachment,
    Conversation,
    Mention,
    Message,
    Participant,
    Reaction,
)
from nextcloud_talk_core.permissions import PERM_FLAGS, permissions_from_flags
from nextcloud_talk_core.talk import TalkClient

__all__ = [
    "PERM_FLAGS",
    "Attachment",
    "Conversation",
    "Mention",
    "Message",
    "NextcloudAuthError",
    "NextcloudConfigError",
    "NextcloudNotFoundError",
    "NextcloudOCSError",
    "NextcloudTalkError",
    "NextcloudTransportError",
    "OCSClient",
    "Participant",
    "Reaction",
    "Settings",
    "TalkClient",
    "__version__",
    "permissions_from_flags",
]
