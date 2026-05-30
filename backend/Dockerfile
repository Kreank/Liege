# Multi-Stage: Node-Stage baut Angular, Python-Stage serviert.
# Vorher musste der Host vor jedem `docker compose build` ein
# `cd frontend && npm run build` laufen lassen — das ist jetzt im Image.

FROM node:24-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim
WORKDIR /app/backend

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Angular-Build aus der Frontend-Stage holen. FastAPI mountet das
# als Statik unter / und liefert auch /login + /admin von dort.
COPY --from=frontend-build /build/dist /app/frontend/dist
# Public-Assets, die Angular nicht ins dist kopiert (Legacy login/admin
# kommen über frontend/public/, das landet automatisch in dist/browser/).
COPY assets/ /app/assets/

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
