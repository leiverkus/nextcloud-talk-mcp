# Briefing: Nextcloud Talk MCP Server

## Ziel

Aus dem beiliegenden Prototyp (`nextcloud_talk_mcp.py`) ein vollständiges, veröffentlichungsreifes GitHub-Repo machen. Der Server wrappt die Nextcloud-Talk-/Spreed-OCS-API als MCP-Tools, primär für die Nutzung mit Claude Desktop auf macOS. Kontext: Nutzung im Rahmen der Universität Oldenburg (institutionelle Nextcloud-Instanz, vermutlich SSO/SAML — App-Passwörter umgehen das serverseitig).

Es existiert **kein** anderer MCP-Server für Talk. Die etablierten Nextcloud-MCP-Server (cbcoutinho, No-Smoke, hithereiamaliff) decken Notes/Calendar/Contacts/Tables/WebDAV ab, aber nicht Spreed/Talk. Diese Lücke füllt dieses Projekt.

## Ausgangszustand

Der Prototyp ist ein einzelnes Python-File mit FastMCP und httpx. Vier Tools sind vorhanden und grundsätzlich funktionsfähig:

- `list_conversations` — Räume auflisten (token, name, type, unread, lastMessage)
- `read_messages(token, limit)` — letzte Nachrichten lesen
- `send_message(token, message, reply_to)` — Nachricht senden
- `list_mentions(token, limit)` — @-Autocomplete-Kandidaten

Auth über App-Passwort (Basic Auth), Konfiguration über Umgebungsvariablen `NC_URL`, `NC_USER`, `NC_APP_PASSWORD`. OCS-Header (`OCS-APIRequest: true`) sind gesetzt.

## Aufgaben

### 1. Projektstruktur aufbauen

Aus dem Single-File ein sauberes Python-Package machen:

```
nextcloud-talk-mcp/
├── src/nextcloud_talk_mcp/
│   ├── __init__.py
│   ├── __main__.py          # entry point
│   ├── server.py            # FastMCP instance + tool registration
│   ├── client.py            # OCS HTTP client (auth, error handling, retries)
│   └── tools/               # tools nach Domäne getrennt, falls es wächst
├── tests/
├── pyproject.toml           # PEP 621, mit console_scripts entry point
├── README.md
├── LICENSE                  # MIT (Copyright Patrick Leiverkus)
├── .env.example
├── .gitignore
└── .github/workflows/ci.yml
```

`pyproject.toml` mit `nextcloud-talk-mcp` als entry point, sodass `uvx`/`pipx` direkt funktioniert. Python >=3.10 (wegen `int | None` Syntax).

### 2. Client robuster machen

Den HTTP-Layer aus den Tools rausziehen in `client.py`:

- Zentrale Fehlerbehandlung: OCS-Statuscodes auswerten (`ocs.meta.statuscode`), nicht nur HTTP-Status. Talk gibt teils HTTP 200 mit OCS-Fehler zurück.
- Sinnvolle Exceptions definieren (z.B. `NextcloudAuthError`, `NextcloudNotFoundError`) statt rohe httpx-Errors durchzureichen.
- Timeout und ein einfaches Retry für transiente Fehler (5xx, Netzwerk).
- Config-Validierung beim Start: fehlende Env-Vars → klare Fehlermeldung, nicht KeyError-Traceback.

### 3. Tools erweitern — voller Scope

Die Talk-API soll möglichst vollständig abgebildet werden. Über den Chat-Kern hinaus mindestens:

- **Konversationsverwaltung**: `create_conversation`, `rename_conversation`, `set_description`, `delete_conversation`, `add_participant`, `remove_participant`, `set_participant_permissions`
- **Dateianhänge**: lesen und senden (Talk verlinkt auf WebDAV-Files via `richObject`) — share-File-in-Talk-Endpunkt nutzen
- **Reactions**: hinzufügen, entfernen, auflisten
- **Read-Markers**: als gelesen markieren, ungelesen-Status setzen
- **Nachrichten**: bearbeiten, löschen, Reminder setzen
- **Long-Polling-Variante** von `read_messages` (`lookIntoFuture=1` + `lastKnownMessageId`) für ein „warte auf neue Nachrichten"-Pattern

Endpunkte vor Implementierung gegen die API-Doku verifizieren (API-Versionen variieren je Endpunkt).

Schreibende und destruktive Tools (`send_message`, `create_conversation`, `delete_conversation`, `remove_participant` etc.) klar als solche markieren — sinnvollerweise in Docstring und ggf. via MCP-Annotations (`destructiveHint`, `readOnlyHint`). MCP-Clients fragen vor Ausführung ohnehin um Bestätigung; das ist gewollt und darf nicht umgangen werden, gerade bei Uni-Kanälen. Destruktive Operationen (löschen, entfernen) brauchen besonders deutliche Warnhinweise im Docstring.

### 4. Tests (Pflicht, parallel zur Implementierung)

Jedes Tool wird mit Tests abgesichert — kein Tool ohne Test mergen. Pytest mit gemockten httpx-Responses (`respx` oder `httpx.MockTransport`). Keine Live-Calls gegen die Uni-Instanz in der CI. Abdecken:

- OCS-Parsing (`ocs.data`-Extraktion, `ocs.meta.statuscode`)
- Fehlerpfade: 401 (Auth), 404 (Raum nicht gefunden), OCS-Fehlercode bei HTTP 200
- Rückgabeformat jedes Tools (Schema-Stabilität)
- Destruktive Tools: korrekte Endpunkt-/Methodenwahl (DELETE etc.), ohne echten Call
- Config-Validierung (fehlende Env-Vars → klare Exception)

Ziel: hohe Coverage über alle Tools. `pytest-cov` einbinden und Coverage in der CI ausgeben.

### 5. Dokumentation

README mit:
- Was es ist + Abgrenzung zu den bestehenden Nextcloud-MCP-Servern (Talk-Lücke)
- Install (`uvx`, `pipx`, from source)
- App-Passwort erzeugen (Settings → Security), Hinweis zu SSO/SAML-Instanzen
- Claude-Desktop-`claude_desktop_config.json`-Beispiel (macOS-Pfad)
- Tool-Referenz (Tabelle)
- Sicherheitshinweis: App-Passwort, nicht Login-Passwort; schreibende Tools

### 6. CI (Pflicht)

GitHub Actions mit **Matrix-Build über Python 3.10, 3.11, 3.12 und 3.13** — jede Version läuft lint + test. Schritte:

- `ruff check` (lint) und `ruff format --check`
- `pytest` mit `pytest-cov`, Coverage-Report im Job-Output
- Matrix-Strategie, sodass ein Fehler in einer Version den Build rot macht (`fail-fast: false`, damit man sieht, welche Version bricht)

Caching für pip/uv einbauen, damit die Matrix nicht unnötig langsam ist. Optional zusätzlich ein `publish.yml` (manuell via `workflow_dispatch` getriggert, Trusted Publishing zu PyPI) — angelegt, aber noch nicht scharf geschaltet.

## Hinweise / Constraints

- **Keine Secrets committen.** `.env` in `.gitignore`, nur `.env.example` mit Platzhaltern.
- OCS-API-Doku: `https://nextcloud-talk.readthedocs.io/en/latest/` — Endpunkte gegen die tatsächliche API-Version verifizieren, nicht raten. Talk-API-Versionen (`api/v1` vs `api/v4`) variieren je Endpunkt.
- `type`-Codes der Räume dokumentieren: 1=Einzelchat, 2=Gruppe, 3=öffentlich, 4=Changelog.
- Repo-Name-Vorschlag: `nextcloud-talk-mcp`. GitHub-Account: leiverkus.
- Passt stilistisch zum bestehenden `leiverkus/open-document-skills`-Repo — gleiche Konventionen übernehmen, wo vorhanden.

## Empfohlene Reihenfolge

1. API-Doku checken, vorhandene 4 Tools gegen echte Endpunkte verifizieren
2. Package-Struktur + client.py-Refactor (inkl. Config-Validierung, OCS-Fehlerbehandlung)
3. Tests für den bestehenden Stand schreiben, CI-Matrix (3.10–3.13) gleich aufsetzen — ab hier läuft die CI grün durch
4. Tools inkrementell auf vollen Scope erweitern — jedes neue Tool zusammen mit seinem Test, CI bleibt grün
5. README + LICENSE (MIT) + `.env.example`
6. `git init`, sauberer erster Commit, dann auf GitHub (`leiverkus/nextcloud-talk-mcp`) pushen
