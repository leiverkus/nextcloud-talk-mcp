# nextcloud-talk-core

A reusable, **MCP-free** Python client for the Nextcloud Talk (Spreed) OCS API.

This is the shared core extracted from
[`nextcloud-talk-mcp`](../nextcloud-talk-mcp): the HTTP/OCS layer, typed models,
config, and errors, with no dependency on any MCP framework — so other projects
(e.g. a polling bridge) can depend on it directly.

## Install

```bash
pip install nextcloud-talk-core
```

Or pin to a Git tag without PyPI:

```bash
pip install "git+https://github.com/leiverkus/nextcloud-talk-mcp.git@core-v1.0.1#subdirectory=packages/nextcloud-talk-core"
```

## Use

```python
from nextcloud_talk_core import TalkClient

# Reads NC_URL / NC_USER / NC_APP_PASSWORD (use an app password, not your login).
with TalkClient.from_env() as talk:
    for c in talk.list_conversations():
        print(c.token, c.name, c.unread)

    msg = talk.send_message("<token>", "Hello from nextcloud-talk-core")
    print(msg.id)
```

## Public API

`TalkClient` (one method per Talk operation, returning typed models),
`OCSClient` (low-level OCS HTTP), `Settings`, the models (`Conversation`,
`Message`, `Attachment`, `Participant`, `Mention`, `Reaction`), the error
hierarchy (`NextcloudTalkError` and subclasses), and `permissions_from_flags`.
All re-exported from the package root.

This surface is a **SemVer-stable contract**: breaking changes require a major
version (and a new `core-vX.Y.Z` tag). See [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE) © Patrick Leiverkus
