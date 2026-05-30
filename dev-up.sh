#!/usr/bin/env bash
# Lokales Dev-Setup für Liege.
#
# Was passiert:
# 1. Postgres + Backend im Docker-Compose hochziehen (falls noch nicht).
# 2. Backend-Smoke kurz prüfen.
# 3. Angular ng serve mit Proxy auf Port 4200 starten (hot-reload).
#
# Öffne dann http://localhost:4200/ im Browser. Änderungen in
# frontend/src/ werden live nachgeladen. Backend-Logik-Änderungen
# erfordern `docker compose up -d --build backend` separat (oder
# einfach STRG+C hier und neu starten).

set -euo pipefail
cd "$(dirname "$0")"

echo "==> Postgres + Backend hochziehen…"
docker compose up -d postgres backend

echo "==> Warten bis Backend antwortet…"
for i in {1..30}; do
  if curl -sf -o /dev/null http://localhost:8000/auth/status; then
    echo "    Backend OK."
    break
  fi
  sleep 1
done

echo "==> Backend-Smoke (ws_smoke vs golden)…"
docker exec liege-backend python /app/backend/tools/ws_smoke.py /tmp/smoke.txt
docker cp liege-backend:/tmp/smoke.txt /tmp/smoke.txt
if diff -q docu/ws_smoke_golden.txt /tmp/smoke.txt > /dev/null; then
  echo "    Smoke == golden."
else
  echo "    !! Smoke weicht ab. Schau dir das an:"
  diff docu/ws_smoke_golden.txt /tmp/smoke.txt | head -20
fi

echo "==> ng serve auf http://localhost:4200/ (Proxy → Backend auf 8000)"
echo "    STRG+C beendet nur den Frontend-Server. Backend läuft weiter."
cd frontend && npx ng serve --open
