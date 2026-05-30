# Dev-Setup (lokal)

Stand: 2026-05-30 (nach dem Refactor auf Angular + Phaser).

## Hot-Reload-Workflow (empfohlen)

```bash
./dev-up.sh
```

Was passiert:
1. Postgres + Backend kommen via Docker Compose hoch (FastAPI auf :8000).
2. Backend-Smoke gegen `docu/ws_smoke_golden.txt` läuft kurz — Pass/Fail-Anzeige.
3. `ng serve` öffnet `http://localhost:4200/` im Browser. Frontend wird live neu gebaut bei jedem Save in `frontend/src/`.

Proxy ist in `frontend/proxy.conf.json` konfiguriert: alle Requests auf `/ws`, `/auth/*`, `/assets/*`, `/admin`, `/login`, `/manifest.webmanifest`, `/ngsw-worker.js` werden vom Angular-Dev-Server ans Backend auf 8000 weitergereicht. WebSockets klappen ebenso (`ws: true`).

## Wenn du Backend-Code änderst

```bash
docker compose up -d --build backend
```

Multi-Stage-Dockerfile baut auch das Angular mit (ist im Image). Das `ng serve` aus `dev-up.sh` brauchst du dafür nicht zu stoppen — es greift weiter auf das gleiche Backend.

## Smoke-Test manuell

```bash
docker exec liege-backend python /app/backend/tools/ws_smoke.py /tmp/run.txt
docker cp liege-backend:/tmp/run.txt /tmp/run.txt
diff docu/ws_smoke_golden.txt /tmp/run.txt
```

Diff leer = grün. Liste der erwarteten 16 Steps in `backend/tools/ws_smoke.py`.

## Production-Build lokal probieren (ohne ng serve)

```bash
docker compose up -d --build backend
# → http://localhost:8000/
```

Das ist der Server-Stand — gleicher Mode wie Production. Kein Hot-Reload.

## SESSION_SECRET

`docker-compose.yml` erwartet `${SESSION_SECRET}` als ENV-Var. Lokal sitzt sie in `docker-compose.override.yml` (`.gitignore`-ed). Wenn du eine `.env`-Datei im Repo-Root anlegst und dort `SESSION_SECRET=...` reinschreibst, nimmt Docker Compose den Wert automatisch — Override wird dann überflüssig.

Auf dem Server: `.env` im Repo-Root mit echtem Secret oder über Hosting-ENV.

## Verbleibende bekannte Lücken (siehe `docu/REFACTOR_NOTES.md`)

- Sound-Manager ist nicht migriert — Audio im Browser ist stumm.
- WorldScene-TODOs: Build-Mode Place-Click mit Material/Rotation, Minimap-Sense-Radius/Quest-Marker/Event-Pulse.
- PWA-Manifest minimal (kein iOS-Splash, kein MS-Tile-Color).
- `ServerMessage` ist Bag-Type statt Diskriminator-Union (TS-Polish).
