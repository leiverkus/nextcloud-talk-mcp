# Ergänzung fürs bestehende MCP-Repo: `nextcloud-talk-core` extrahieren

## Kontext

Das MCP-Repo (`leiverkus/nextcloud-talk-mcp`) wird bereits gecodet. Es soll nun einen wiederverwendbaren OCS-Client als sauber abgegrenztes, eigenständig installierbares Package bereitstellen, weil ein weiteres Projekt denselben Client braucht:

- eine Polling-Bridge (Talk → OpenCode, eigenes Repo, Python)
- (indirekt) eine Swift-Menüleisten-App, die die Bridge startet/überwacht

Ziel dieser Ergänzung: den HTTP-/OCS-Layer so herauslösen, dass er als `nextcloud-talk-core` ohne MCP-Abhängigkeiten installierbar ist — **per Git-Dependency** (kein PyPI). Die Bridge zieht den Core direkt aus diesem GitHub-Repo gegen einen Tag, z.B.:

```
nextcloud-talk-core @ git+https://github.com/leiverkus/nextcloud-talk-mcp.git@core-v0.1.0#subdirectory=...
```

(Genaue URL/Subdirectory hängt vom gewählten Layout ab — siehe Packaging unten.) PyPI ist bewusst **nicht** das Ziel: bei nur zwei internen Konsumenten lohnt der Release-Apparat nicht. Lässt sich später nachrüsten, ohne die Paketstruktur zu ändern, falls der Core mal für Dritte gedacht ist.

## Aufgabe

### 1. Core sauber abgrenzen

Den OCS-Client in ein eigenes, MCP-freies Modul ziehen. Der Core kennt **kein** FastMCP, keine Tools, keine MCP-Annotations — nur Nextcloud/Talk:

- `client.py` — OCS-HTTP-Client (Auth via App-Passwort, OCS-Header, Fehlerbehandlung über `ocs.meta.statuscode`, Retries, Timeouts)
- `models.py` — Datenklassen für Conversation, Message, Participant etc. (typed, stabil — sie sind die öffentliche API)
- `errors.py` — `NextcloudAuthError`, `NextcloudNotFoundError`, `NextcloudOCSError` …
- `config.py` — Env-Var-Validierung (`NC_URL`, `NC_USER`, `NC_APP_PASSWORD`)

Die MCP-Tools werden zu dünnen Wrappern, die ausschließlich aus dem Core importieren.

### 2. Packaging-Entscheidung

Der Core muss als **eigenständig installierbares Package per Git-URL** auflösbar sein. Zwei gangbare Layouts:

- **Subdirectory-Layout (bevorzugt):** Ein Repo, der Core liegt in einem eigenen Unterverzeichnis mit eigenem `pyproject.toml` (z.B. `packages/nextcloud-talk-core/`), der MCP-Server bleibt im Wurzel- bzw. einem zweiten Verzeichnis und hängt lokal auf den Core. Die Bridge installiert per `git+...#subdirectory=packages/nextcloud-talk-core`.
- **Single-Package mit sauberem Modul:** Falls das Subdirectory-Setup zu viel Reibung macht, ein Package, in dem `core` ein klar abgegrenztes, MCP-freies Subpackage ist. Die Bridge installiert dann das ganze Package per Git-URL und importiert nur aus `…core`. Weniger sauber (die Bridge zieht ungenutzten MCP-Code mit), aber simpel.

Entscheidend in beiden Fällen: Der **Core bleibt MCP-frei** und über eine **Git-Tag-Referenz** reproduzierbar installierbar. Kein PyPI-Publish.

### 3. Versionierung & Stabilität

- Versionierung über **Git-Tags** (z.B. `core-v0.1.0`), gegen die die Bridge pinnt. SemVer-Semantik.
- Der Core hat eine **öffentliche API** (Client-Methoden, Modelle) — Breaking Changes nur mit Major-Bump und neuem Tag.
- Modelle/Rückgabetypen als stabilen Vertrag behandeln; die Bridge verlässt sich darauf.
- CHANGELOG.md für den Core führen, Einträge an die Tags gekoppelt.

### 4. Reproduzierbarkeit statt Publishing

- **Kein PyPI, kein Publish-Workflow.** Stattdessen: bei einem stabilen Core-Stand einen Git-Tag setzen; die Bridge referenziert genau diesen Tag in ihrer Dependency.
- Sicherstellen, dass `pip install "git+https://github.com/leiverkus/nextcloud-talk-mcp.git@<tag>#subdirectory=..."` sauber durchläuft (Build-Backend, Metadaten korrekt) — das ist der De-facto-Test des Layouts.
- Optional ein kurzer CI-Job, der genau diese Git-Installation in einem frischen venv verifiziert, damit das Bridge-Repo sich darauf verlassen kann.

### 5. Tests

- Core-Tests bleiben/wandern mit dem Core (gemockte httpx-Responses, OCS-Fehlerpfade).
- CI-Matrix Python 3.10–3.13 weiterhin für beide Packages.

## Wichtig

- Keine Secrets, kein `.env` committen.
- Der Core darf **nichts** MCP-Spezifisches importieren — das ist die Trennlinie, die das Wiederverwenden überhaupt erst ermöglicht.
- Die OCS-API-Versionen (`api/v1` vs `api/v4`) je Endpunkt weiterhin gegen die Doku verifizieren.
