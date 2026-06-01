# Changelog — nextcloud-talk-mcp

## 1.0.2 — 2026-06-01

### Fixed

- The `nextcloud-talk-mcp` console entry point now prints a clear
  `Configuration error: …` message and exits 2 when `NC_URL` / `NC_USER` /
  `NC_APP_PASSWORD` are missing, instead of dumping a `NextcloudConfigError`
  traceback. (`main()` catches `NextcloudConfigError`.)

### Changed

- Pinned `fastmcp>=2,<4` (was `>=0.2`) so a future FastMCP major can't silently
  break the server.
- Rewrote the package README (shown on PyPI) to be self-contained with absolute
  links, instead of short text with relative repo links that don't resolve on
  PyPI.

## 1.0.1 — 2026-06-01

First PyPI release. `pip install nextcloud-talk-mcp` now works (depends on
`nextcloud-talk-core>=1.0.1` from PyPI).

### Added

- Published to PyPI via Trusted Publishing (OIDC), triggered by GitHub Releases.

### Fixed

- `scripts/smoke_live.py` imported the pre-extraction modules
  (`nextcloud_talk_mcp.client/config/errors`) and set `server._client`; it now
  imports from `nextcloud_talk_core` and wires a `TalkClient` onto
  `server._talk`, and closes it in a `finally`. A CI step runs the script
  without env vars and requires the config-error exit so this can't regress.

### Changed

- `nextcloud-talk-core` is now a versioned PyPI dependency
  (`>=1.0.1,<2`) instead of a bare name.
- Packaging modernised for PEP 639: `license = "MIT"` (SPDX) + `license-files`
  instead of the deprecated `license` table and `License ::` classifier;
  `setuptools>=77`. Wheels now build without deprecation warnings.

## 1.0.0 — 2026-05-30

First stable release: 24 tools covering the full Talk scope, built on
`nextcloud-talk-core`. All tools verified live against a real instance.

### Changed

- **Refactored onto `nextcloud-talk-core`.** The OCS/HTTP layer, the typed
  models, config, errors, and the permission-bitmask helper now live in the
  separate, MCP-free `nextcloud-talk-core` package (installable via Git tag).
  The MCP tools became thin wrappers over `TalkClient` that serialise its typed
  models to the unchanged camelCase MCP output. Tool names, signatures,
  docstrings, annotations, and output schema are **unchanged** — purely an
  internal restructure into a monorepo (`packages/`). Tests split per package
  (core: httpx mocks; mcp: mocked `TalkClient`).

---

Tool-Erweiterung in zwei Sub-Runden: **20 neue Tools** über sieben Domänen,
jedes mit Test abgesichert. Endpunkte gegen die Spreed-OCS- bzw. OCS-Share-Doku
verifiziert; API-Versionen variieren pro Domäne (Konversation/Teilnehmer:
`api/v4`, Chat/Read-Marker/Reactions/Reminder: `api/v1`, Dateianhänge:
`files_sharing api/v1`). Damit ist der volle Talk-Scope des Briefings abgedeckt.

### Added — Sub-Runde B (Reactions, Reminder, Dateianhänge)

- **Reactions** (`api/v1/reaction`, seit NC 24): `add_reaction`,
  `remove_reaction`, `list_reactions` (nach Emoji gekeyt).
- **Reminder** (`api/v1/chat/.../reminder`, Capability `remind-me-later`):
  `set_reminder` (Unix-Timestamp), `get_reminder`, `delete_reminder`.
- **Dateianhänge senden**: `share_file_to_conversation` teilt eine bereits im
  WebDAV liegende Datei in den Raum (`POST files_sharing/api/v1/shares`,
  `shareType=10`); optionale `caption` via `talkMetaData`. Lädt nichts hoch.
- **Anhänge-Parsing**: `read_messages` (und `wait_for_messages`) liefern nun pro
  Nachricht eine `attachments`-Liste — File-`richObject`s aus
  `messageParameters` werden defensiv extrahiert (Name/Pfad/MIME/Größe, soweit
  vorhanden).
- **`OCSClient`**: optionaler `app`-Override auf `request()`/`post()`, damit
  `share_file_to_conversation` den `files_sharing`-Endpunkt statt `spreed`
  ansprechen kann — ohne zweiten Client, dieselbe Retry-/OCS-Parsing-Logik.
- 15 weitere Tests (Reactions/Reminder/Share-Endpunkte, `app`-Override,
  Anhänge-Parsing inkl. Teilfelder, OCS-201). Gesamt: 73 Tests, 95 % Coverage.

### Fixed

- **`OCSClient` akzeptiert den vollen 2xx-Erfolgsbereich.** Bisher galten nur
  OCS-Statuscodes 100 und 200 als Erfolg; schreibende Endpunkte wie
  `create_conversation`, `add_reaction` und `set_reminder` antworten mit
  **201 (Created)** und lösten fälschlich einen `NextcloudOCSError` aus. Live
  gegen `cloud.uol.de` aufgefallen. Erfolg ist jetzt `statuscode == 100` oder
  `200 ≤ statuscode < 300`.

### Added — Sub-Runde A (Konversation, Teilnehmer, Edit/Delete, Read-Marker, Long-Poll)

### Added

- **Konversationsverwaltung** (`api/v4`): `create_conversation`,
  `rename_conversation`, `set_description`, `delete_conversation`.
- **Teilnehmerverwaltung** (`api/v4`): `list_participants`, `add_participant`,
  `remove_participant`, `set_participant_permissions`. Letzteres nimmt
  lesbare boolesche Flags (`can_publish_audio`, `can_post_chat` …) entgegen
  und baut daraus intern die Talk-Berechtigungs-Bitmaske; `mode` =
  set / add / remove.
- **Nachrichten** (`api/v1`): `edit_message`, `delete_message`.
- **Read-Marker** (`api/v1`): `mark_as_read`, `mark_as_unread`.
- **Long-Polling** (`api/v1`): `wait_for_messages` — blockiert serverseitig bis
  zu `timeout` Sekunden (max 60) auf neue Nachrichten nach
  `last_known_message_id`.
- **MCP-Annotationen**: read-Tools tragen `readOnlyHint`, destruktive Tools
  (`delete_message`, `delete_conversation`, `remove_participant`)
  `destructiveHint` — MCP-Clients fragen vor Ausführung um Bestätigung.

### Changed

- **`OCSClient`**: neue `put()`/`delete()`-Wrapper (DELETE mit Body für
  `remove_participant`); optionaler Per-Call-`timeout`-Override auf `get()`/
  `request()`, damit der Long-Poll länger warten darf als der Default-Timeout.
- **`read_messages`** und `wait_for_messages` teilen sich jetzt den
  `_format_message`-Helfer (identisches Nachrichten-Schema).

### Tests

- 23 neue Tests (Methode/Endpunkt/Body/Schema jedes Tools, Bitmask-Berechnung,
  Long-Poll-Parameter, put/delete-Wrapper, Timeout-Override). Gesamt: 58 Tests,
  94 % Coverage.

---

## v0.1.0 - 2026-05-30

Erstes veröffentlichungsreifes Release. Füllt die Talk-Lücke unter den
bestehenden Nextcloud-MCP-Servern: cbcoutinho, No-Smoke und hithereiamaliff
decken Notes, Calendar, Contacts, Tables und WebDAV ab — keiner davon die
Spreed/Talk-API. Dieses Paket schließt die Lücke.

Primäre Zielplattform: Claude Desktop auf macOS, institutionelle
Nextcloud-Instanzen mit SSO/SAML und Zwei-Faktor-Authentifizierung (App-Passwörter
umgehen den IdP serverseitig).

Live-verifiziert gegen `cloud.uol.de` (Universität Oldenburg).

### Added

- **Vier MCP-Tools** über die Spreed OCS API:
  - `list_conversations()` — alle Talk-Räume des Nutzers auflisten
    (`token`, `name`, `type`, `unread`, `lastMessage`). Endpunkt:
    `api/v4/room` (Nextcloud ≥ 22). Raumtypen dokumentiert: 1 = Einzelchat,
    2 = Gruppe, 3 = öffentlich, 4 = Changelog, 6 = „Notiz an mich".
  - `read_messages(token, limit=30)` — letzte Nachrichten lesen.
    Endpunkt: `api/v1/chat/{token}`.
  - `send_message(token, message, reply_to=None)` — Nachricht senden,
    optional als Antwort auf eine Message-ID. Als Write-Operation
    gekennzeichnet, damit MCP-Clients vor Ausführung fragen.
  - `list_mentions(token, limit=20)` — @-Autocomplete-Kandidaten
    (Nutzer/Räume).

- **`OCSClient`** (`src/nextcloud_talk_mcp/client.py`) — robuster HTTP-Layer
  über `httpx.Client` (Keep-Alive, kein Client-Rebuild pro Call):
  - OCS-Envelope-Parsing: `ocs.meta.statuscode` wird ausgewertet — Talk
    gibt teils HTTP 200 mit OCS-Fehlercode zurück, der Prototyp ignorierte
    das.
  - Typisierte Exception-Hierarchie statt roher `httpx`-Fehler (s. u.).
  - Timeout 30 s, Exponential-Backoff-Retry (bis zu 2 Versuche, 0,5 s · 2ⁿ
    + Jitter) für idempotente Methoden bei HTTP 5xx und `TransportError`.
    POST-Calls werden nicht retried.
  - `User-Agent: nextcloud-talk-mcp/<version>`.

- **Exception-Hierarchie** (`src/nextcloud_talk_mcp/errors.py`):
  `NextcloudTalkError` → `NextcloudConfigError`, `NextcloudAuthError`,
  `NextcloudNotFoundError`, `NextcloudOCSError`, `NextcloudTransportError`.

- **Config-Validierung** (`src/nextcloud_talk_mcp/config.py`) —
  `Settings.from_env()` liest `NC_URL`, `NC_USER`, `NC_APP_PASSWORD`;
  jede fehlende oder ungültige Variable → `NextcloudConfigError` mit
  präziser Handlungsanweisung. Kein `KeyError`-Traceback beim Import mehr
  (Schwäche des Prototyps).

- **Package-Struktur** (`src/nextcloud_talk_mcp/`, `pyproject.toml`) —
  src-Layout, PEP 621, `console_scripts`-Entry-Point `nextcloud-talk-mcp`,
  sodass `uvx nextcloud-talk-mcp` und `pipx install nextcloud-talk-mcp`
  direkt funktionieren. Python ≥ 3.10.

- **35 Tests**, 92 % Statement-Coverage (`pytest` + `httpx.MockTransport`,
  keine Live-Calls in der CI):
  - OCS-Parsing aller Statuscodes (100, 200, 401, 403, 404, 5xx).
  - HTTP-Fehler → korrekte Exception.
  - Retry-Logik: Anzahl der Versuche, Verhalten bei POST.
  - Schema-Stabilität aller vier Tools.
  - Config-Validierung: alle Fehlerpfade.

- **CI-Matrix** (`.github/workflows/ci.yml`) — Python 3.10, 3.11, 3.12,
  3.13 auf Ubuntu; `fail-fast: false`; ruff check + format als separater
  Lint-Job; pip-Cache.

- **`publish.yml`** — PyPI Trusted Publishing (OIDC) via
  `workflow_dispatch`; noch nicht scharf geschaltet.

- **Dokumentation**: `README.md` mit Abgrenzung zu bestehenden
  Nextcloud-MCP-Servern, Install-Anleitung (uvx / pipx / from source),
  App-Passwort-Anleitung mit SSO/SAML-Hinweis, Claude-Desktop-Config
  (macOS), Tool-Referenz-Tabelle, Sicherheitssektion.
  `LICENSE` (MIT, Copyright Patrick Leiverkus). `.env.example`.
