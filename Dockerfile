# Образ приложения: собирается из закоммиченного кода (`just stage` / CI). Непривилегированный пользователь.
FROM node:25-bookworm-slim AS frontend
RUN npm install -g pnpm@12.5.1
WORKDIR /frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend ./
RUN pnpm build

FROM python:3.12-slim-bookworm AS build
RUN pip install --no-cache-dir uv==0.12.17
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev

FROM python:3.12-slim-bookworm
RUN useradd --system --uid 10001 app
WORKDIR /app
COPY --from=build --chown=app /app /app
COPY --chown=app alembic.ini ./
COPY --chown=app migrations ./migrations
COPY --from=frontend --chown=app /frontend/dist ./frontend/dist
USER app
ENV PATH="/app/.venv/bin:$PATH" HOST=0.0.0.0 PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["kognis"]
