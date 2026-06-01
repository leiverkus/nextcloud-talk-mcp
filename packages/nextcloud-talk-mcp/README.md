# nextcloud-talk-mcp

An MCP server for **Nextcloud Talk (Spreed)** — 24 tools covering conversations,
messages, participants, reactions, reminders, and file sharing, for use with
Claude Desktop and any other MCP client.

It is the first MCP server to cover Talk; the established Nextcloud MCP servers
cover Notes / Calendar / Contacts / Tables / WebDAV but not Spreed. A thin
wrapper over [`nextcloud-talk-core`](https://pypi.org/project/nextcloud-talk-core/),
where all endpoint logic and the typed models live.

## Install

```bash
uvx nextcloud-talk-mcp          # run without installing
pipx install nextcloud-talk-mcp # or install globally
pip install nextcloud-talk-mcp  # or into a venv
```

## Configure

The server reads three environment variables:

| Variable | Example | Notes |
|---|---|---|
| `NC_URL` | `https://cloud.example.com` | Base URL, no trailing slash. |
| `NC_USER` | `your-username` | Your Nextcloud username. |
| `NC_APP_PASSWORD` | `xxxxx-xxxxx-xxxxx-xxxxx` | An **app password** (Settings → Security), not your login password. Works through SSO/2FA. |

## Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

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

## Tools

Conversations (`list_conversations`, `create_conversation`, `rename_conversation`,
`set_description`, `delete_conversation`), messages (`read_messages`,
`send_message`, `edit_message`, `delete_message`, `wait_for_messages`,
`list_mentions`), read-markers (`mark_as_read`, `mark_as_unread`), participants
(`list_participants`, `add_participant`, `remove_participant`,
`set_participant_permissions`), reactions (`add_reaction`, `remove_reaction`,
`list_reactions`), reminders (`set_reminder`, `get_reminder`, `delete_reminder`),
and file sharing (`share_file_to_conversation`). Read-only tools carry
`readOnlyHint`; destructive ones carry `destructiveHint` so clients prompt first.

Full tool reference, security notes, and source:
<https://github.com/leiverkus/nextcloud-talk-mcp>

## License

MIT © Patrick Leiverkus
