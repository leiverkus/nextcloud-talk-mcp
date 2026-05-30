# Changelog

## Unreleased

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
