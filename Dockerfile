# Multi-stage image: builds the React SPA (node) then installs the locked
# Python stack via uv from uv.lock (offline at runtime; build needs network).
FROM node:22-slim AS fe
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim AS app
WORKDIR /code
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
COPY backend ./backend
COPY --from=fe /fe/dist ./frontend/dist
RUN uv sync --frozen --no-dev --project /code
ENV PATH=/code/.venv/bin:$PATH
ENV AIRP_DATA_DIR=/data AIRP_CLAIM_BASE_URL=
VOLUME ["/data"]
EXPOSE 8000
WORKDIR /code
ENTRYPOINT ["/bin/sh", "-c", "alembic -c backend/alembic.ini upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend"]
