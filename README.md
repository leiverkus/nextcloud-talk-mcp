# Nextcloud Talk MCP

[![CI](https://github.com/leiverkus/nextcloud-talk-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/leiverkus/nextcloud-talk-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](pyproject.toml)

**An MCP server for Nextcloud Talk (Spreed) — list conversations, read and send messages, and resolve @-mentions straight from your agent.**

The established Nextcloud MCP servers ([cbcoutinho](https://github.com/cbcoutinho/nextcloud-mcp-server), [No-Smoke](https://github.com/No-Smoke/nextcloud-mcp), [hithereiamaliff](https://github.com/hithereiamaliff/nextcloud-mcp)) cover Notes, Calendar, Contacts, Tables, and WebDAV — **but not Talk**. This project fills that gap: it wraps the Talk/Spreed OCS API as MCP tools, primarily for use with Claude Desktop on macOS.

Auth is via a Nextcloud **app password** (Basic Auth), which works even on SSO/SAML instances with two-factor authentication — the app password bypasses the identity provider server-side, so no interactive login or second factor is needed for API access.

## Tools

| Tool | Kind | Description |
|---|---|---|
| `list_conversations()` | read | List all Talk conversations (rooms) the user is part of — `token`, `name`, `type`, `unread`, `lastMessage`. |
| `read_messages(token, limit=30)` | read | Read the most recent messages in a conversation. |
| `send_message(token, message, reply_to=None)` | **write** | Send a message to a conversation, optionally as a reply to a message id. |
| `list_mentions(token, limit=20)` | read | List users/rooms that can be `@`-mentioned in a conversation (autocomplete candidates). |

`token` always comes from `list_conversations()`. Conversation `type` codes: **1** = one-to-one, **2** = group, **3** = public, **4** = changelog, **6** = "Note to self".

> **Write and destructive tools require confirmation.** Write tools carry a `readOnlyHint: false` annotation; destructive ones (`delete_message`, `delete_conversation`, `remove_participant`) additionally carry `destructiveHint: true`, so MCP clients prompt before running them. That confirmation step is intentional — do not bypass it, especially on shared or institutional channels.

## Installation

Requires **Python ≥ 3.10**.

### uvx (no install)

```bash
uvx nextcloud-talk-mcp
```

### pipx

```bash
pipx install nextcloud-talk-mcp
```

### From source

```bash
git clone https://github.com/leiverkus/nextcloud-talk-mcp.git
cd nextcloud-talk-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Configuration

The server reads three environment variables:

| Variable | Example | Notes |
|---|---|---|
| `NC_URL` | `https://cloud.example.com` | Base URL, **no** trailing slash. |
| `NC_USER` | `your-username` | Your Nextcloud username. |
| `NC_APP_PASSWORD` | `xxxxx-xxxxx-xxxxx-xxxxx` | An **app password**, not your login password. |

See [`.env.example`](.env.example) for a template. Missing or malformed variables produce a clear error at startup — not a traceback.

### Creating an app password

1. In Nextcloud, open **Settings → Security → Devices & sessions**.
2. Under **App passwords / App tokens**, enter a name (e.g. `talk-mcp`) and click **Create new app password**.
3. Copy the generated password immediately — it is shown only once.

**On SSO/SAML instances (e.g. universities), this is the only way to use the API.** The app password authenticates against Nextcloud directly, bypassing the identity provider and any two-factor prompt. Never use your actual login password.

## Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "nextcloud-talk": {
      "command": "uvx",
      "args": ["nextcloud-talk-mcp"],
      "env": {
        "NC_URL": "https://cloud.example.com",
        "NC_USER": "your-username",
        "NC_APP_PASSWORD": "xxxxx-xxxxx-xxxxx-xxxxx"
      }
    }
  }
}
```

If you installed from source into a virtualenv, point `command` at that interpreter instead:

```json
{
  "mcpServers": {
    "nextcloud-talk": {
      "command": "/absolute/path/to/nextcloud-talk-mcp/.venv/bin/python",
      "args": ["-m", "nextcloud_talk_mcp"],
      "env": {
        "NC_URL": "https://cloud.example.com",
        "NC_USER": "your-username",
        "NC_APP_PASSWORD": "xxxxx-xxxxx-xxxxx-xxxxx"
      }
    }
  }
}
```

Restart Claude Desktop; the four tools then appear under the `nextcloud-talk` server.

## Security

- **Use an app password, never your login password.** App passwords are revocable per-device under Settings → Security and never expose your real credentials.
- **Keep secrets out of version control.** `.env` is gitignored; only `.env.example` (placeholders) is committed.
- **Write tools prompt before running.** `send_message` is marked as a write operation so MCP clients ask for confirmation first. This is by design — leave it on.

## License

[MIT](LICENSE) © Patrick Leiverkus
