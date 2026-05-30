# Changelog — nextcloud-talk-core

Versioned via Git tags (`core-vX.Y.Z`); SemVer. The public API is `TalkClient`,
`OCSClient`, `Settings`, the models, the errors, and `permissions_from_flags`.
Breaking changes to that surface require a major bump.

## core-v0.1.0 (unreleased)

Initial extraction from the `nextcloud-talk-mcp` server into a reusable,
**MCP-free** package, so other consumers (a Talk→OpenCode polling bridge, and
indirectly a Swift menu-bar app) can depend on the same client via a Git tag —
no PyPI.

### Added

- **`OCSClient`** — low-level OCS HTTP client: Basic-Auth via app password,
  `OCS-APIRequest` header, retries with backoff, per-call timeout override,
  and an `app` override for the `files_sharing` endpoint. Maps the OCS
  `meta.statuscode` to typed exceptions; success is `100` or `200 ≤ code < 300`
  (201 Created is success).
- **`TalkClient`** — high-level domain client: one method per Talk operation
  (conversations, messages, read-markers, participants, reactions, reminders,
  file sharing, long-poll). Owns endpoint paths + payloads and returns typed
  models. API versions verified per domain (v4 conversation/participant, v1
  chat/reactions/reminders, files_sharing for attachments).
- **Models** (`models.py`) — `Conversation`, `Message`, `Attachment`,
  `Participant`, `Mention`, `Reaction` dataclasses with `from_api()` parsing;
  snake_case fields as the stable contract.
- **`Settings.from_env()`** — validates `NC_URL` / `NC_USER` /
  `NC_APP_PASSWORD` with clear errors.
- **`permissions_from_flags()`** — builds the attendee permission bitmask from
  named boolean capability flags.
- **Errors** — `NextcloudTalkError` hierarchy (`Auth`, `NotFound`, `OCS`,
  `Config`, `Transport`).
