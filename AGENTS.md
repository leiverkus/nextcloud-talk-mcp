# AGENTS.md

Guidance for AI agents working **on this repository**.

`nextcloud-talk-mcp` is an MCP server that wraps the Nextcloud Talk (Spreed)
OCS API as tools, primarily for Claude Desktop. It is the first MCP server to
cover Talk — the established Nextcloud MCP servers cover Notes/Calendar/
Contacts/Tables/WebDAV but not Spreed.

## Layout

```
src/nextcloud_talk_mcp/
  server.py    # FastMCP instance + all @mcp.tool() functions (24 tools)
  client.py    # OCSClient — HTTP, retries, OCS envelope → typed exceptions
  config.py    # Settings.from_env() with validation
  errors.py    # exception hierarchy
tests/         # pytest + httpx.MockTransport (no live calls)
scripts/smoke_live.py  # manual live check against a real instance (not a test)
```

## Commands

```bash
# Tests — pytest with mocked httpx, never hits a real server
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m pytest tests/ --cov=nextcloud_talk_mcp --cov-report=term-missing

# Lint — BOTH are CI gates; format is separate from check
.venv/bin/ruff check .
.venv/bin/ruff format --check .

# Install editable (src layout)
pip install -e ".[dev]"
```

Run Python via `.venv/bin/python` (or activate the venv). The package uses a
`src/` layout, so an in-tree `python` invocation only resolves the installed
package — never run scripts from a cwd that shadows it.

## Conventions — do not break these

- **OCS envelope is the core value-add.** Talk often returns HTTP 200 with an
  error in `ocs.meta.statuscode`. `OCSClient._handle_response` maps the OCS
  statuscode to typed exceptions (`NextcloudAuthError`, `NextcloudNotFoundError`,
  `NextcloudOCSError`). Success is `statuscode == 100` or `200 <= statuscode <
  300` — **201 Created is a success** (create_conversation, add_reaction,
  set_reminder return it). Don't narrow this back to `{100, 200}`.
- **Never raise raw httpx errors to the tool layer.** Everything goes through
  the exception hierarchy in `errors.py`.
- **API version varies by domain — verify, don't guess.** conversation +
  participant management is `api/v4` (Nextcloud 22+); chat, read-markers,
  reactions, reminders are `api/v1`. File sharing uses the *separate*
  `files_sharing` OCS app via the `app=` override on `OCSClient.request()`.
  Check endpoints against <https://nextcloud-talk.readthedocs.io/en/latest/>
  before adding a tool.
- **Mark write/destructive tools.** Reads carry `@mcp.tool(annotations=
  {"readOnlyHint": True})`; destructive ones (`delete_conversation`,
  `delete_message`, `remove_participant`) carry `{"destructiveHint": True}` and
  a docstring warning in caps. MCP clients prompt before running these — that
  confirmation is intentional and must not be engineered around.
- **Tool return values are slim dicts/lists** — extract only useful fields from
  the OCS data, like the existing tools. Don't pass raw API payloads through.
- **No secrets, ever.** `.env` is gitignored; only `.env.example` is committed.
  CI never makes live calls — all tests use `httpx.MockTransport`.
- New code must pass `ruff check` and `ruff format --check`.

## Tests — no tool without a test

Every tool gets at least one test through the `wired`/`make_client` fixtures in
`tests/conftest.py`, asserting: HTTP method, endpoint URL, request body/params,
and return schema. Destructive tools must assert the correct method+path is
sent (without a real call). The fixture swaps in an `httpx.MockTransport` and
records requests — see `tests/test_server.py` for the pattern. Keep coverage
≥ 90%.

When you change a message-shaping helper (`_format_message`,
`_extract_attachments`), the existing `read_messages`/`wait_for_messages` tests
compare exact dicts — update their expected values in the same change.

## Live verification

`scripts/smoke_live.py` runs against a real instance (reads env vars; an app
password, not a login password — works through SSO/2FA). Default run is
read-only. `--lifecycle` creates a throwaway room, exercises the write/new
tools against *that room only*, and deletes it in a `finally` block.
`--share-file PATH` additionally shares an existing WebDAV file and reads it
back. Destructive tools must only ever touch the self-created test room, never
real conversations. Mock tests catch schema/logic; the live run catches what
mocks can't (e.g. the OCS-201 success case was found this way).

## Releases

Version lives in `pyproject.toml` and `src/nextcloud_talk_mcp/__init__.py`
(`__version__`) — keep them in sync. CHANGELOG follows Keep-a-Changelog;
collect changes under `## Unreleased`, then cut a version section on release.
`.github/workflows/publish.yml` publishes to PyPI via Trusted Publishing (OIDC,
no stored token) and is currently `workflow_dispatch`-only — arming it is a
deliberate manual step.
