# AGENTS.md

Guidance for AI agents working **on this repository**.

`nextcloud-talk-mcp` is an MCP server that wraps the Nextcloud Talk (Spreed)
OCS API as tools, primarily for Claude Desktop. It is the first MCP server to
cover Talk — the established Nextcloud MCP servers cover Notes/Calendar/
Contacts/Tables/WebDAV but not Spreed.

## Layout

A monorepo with two packages under `packages/`. **The core is MCP-free — that
separation is the whole point; never import fastmcp (or anything MCP) from the
core.**

```
packages/nextcloud-talk-core/        # reusable, MCP-free — published via Git tag, not PyPI
  src/nextcloud_talk_core/
    talk.py        # TalkClient — one domain method per Talk operation → models
    client.py      # OCSClient — HTTP, retries, OCS envelope → typed exceptions
    models.py      # Conversation/Message/Attachment/Participant/Mention/Reaction (from_api)
    permissions.py # permissions_from_flags() → attendee bitmask
    config.py      # Settings.from_env()
    errors.py      # exception hierarchy
  tests/           # test_talk, test_client, test_config, test_permissions
packages/nextcloud-talk-mcp/         # the MCP server — thin wrappers over TalkClient
  src/nextcloud_talk_mcp/server.py   # @mcp.tool() funcs: call TalkClient, serialise to MCP dicts
  tests/test_server.py               # MagicMock TalkClient, assert call + serialisation
scripts/smoke_live.py                # manual live check against a real instance (not a test)
```

The public API of the core (SemVer-stable, the bridge depends on it):
`TalkClient`, `OCSClient`, `Settings`, the models, the errors,
`permissions_from_flags` — all re-exported from `nextcloud_talk_core/__init__.py`.

## Commands

```bash
# Install both packages editable (mcp depends on core)
pip install -e packages/nextcloud-talk-core -e packages/nextcloud-talk-mcp

# Tests — pytest with mocked httpx / mocked TalkClient, never hits a real server.
# Run per package: both have a top-level `tests` package, so one pytest
# invocation can't import both.
.venv/bin/python -m pytest packages/nextcloud-talk-core/tests --cov=nextcloud_talk_core
.venv/bin/python -m pytest packages/nextcloud-talk-mcp/tests  --cov=nextcloud_talk_mcp

# Lint — BOTH are CI gates; format is separate from check
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Run Python via `.venv/bin/python` (or activate the venv). Both packages use a
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
- **Keep the MCP server thin.** Endpoint paths, payloads, OCS handling, and the
  permission bitmask live in the core (`TalkClient`, `permissions.py`). A tool
  in `server.py` should only: call a `TalkClient` method, then serialise the
  returned model to the established MCP dict. No HTTP/endpoint knowledge there.
- **Two output contracts, on purpose.** Core models use snake_case (the stable
  public API); the MCP tools emit camelCase dicts (`lastMessage`, `attendeeId`).
  The serialisation helpers in `server.py` bridge them — don't leak snake_case
  into MCP output or vice versa.
- **No secrets, ever.** `.env` is gitignored; only `.env.example` is committed.
  CI never makes live calls — all tests use `httpx.MockTransport` (core) or a
  mocked `TalkClient` (mcp).
- New code must pass `ruff check` and `ruff format --check`.

## Tests — no tool without a test

- **Core** (`packages/nextcloud-talk-core/tests`): `TalkClient` methods are
  tested through the `make_talk`/`make_client` fixtures in `conftest.py`
  (`httpx.MockTransport`), asserting HTTP method, endpoint URL, request
  body/params, and the returned model. This is where endpoint/schema coverage
  lives.
- **MCP** (`packages/nextcloud-talk-mcp/tests`): `test_server.py` installs a
  `MagicMock` as the `_talk` global and asserts each tool calls the right
  `TalkClient` method with the right args and serialises to the expected MCP
  dict (incl. the permission-bitmask translation). No httpx mocking here.
- Keep coverage ≥ 90% per package.

Schema changes (e.g. a new field on `Message`/`Attachment`) ripple through
`models.from_api`, the `server.py` serialisers, and both test suites — update
them together.

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

- **Core** (`nextcloud-talk-core`) is released via **Git tags** (`core-vX.Y.Z`),
  not PyPI — the bridge pins to a tag. Its public API is a SemVer contract:
  breaking changes to `TalkClient`/models need a major bump. Keep the version in
  `packages/nextcloud-talk-core/pyproject.toml` and its CHANGELOG in sync with
  the tag. The CI `git-install-verify` job exercises the exact
  `pip install "git+...#subdirectory=packages/nextcloud-talk-core"` path the
  bridge uses.
- **MCP server** version lives in `packages/nextcloud-talk-mcp/pyproject.toml`
  and `…/__init__.py` (`__version__`) — keep them in sync. Its CHANGELOG follows
  Keep-a-Changelog. `.github/workflows/publish.yml` (PyPI Trusted Publishing,
  `workflow_dispatch`-only) is not armed; doing so is a deliberate manual step.
- Each package keeps its **own CHANGELOG** under its directory.
