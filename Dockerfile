FROM python:3.13-slim AS base

# uv via Astral's official image - pinned, no install script.
COPY --from=ghcr.io/astral-sh/uv:0.7.9 /uv /uvx /usr/local/bin/

# Build deps for psycopg2 + git/ssh for the private latentcurvemodel repo.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        git \
        openssh-client \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /root/.ssh \
    && ssh-keyscan github.com >> /root/.ssh/known_hosts

WORKDIR /app

# Dependency layer: cached on lockfile/pyproject changes only.
COPY pyproject.toml uv.lock ./
COPY packages/dashboard/pyproject.toml packages/dashboard/
COPY packages/dash-spatial-prediction/pyproject.toml packages/dash-spatial-prediction/

RUN --mount=type=ssh \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen --group prod --no-install-project

# Application layer.
COPY . .

RUN --mount=type=ssh \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen --group prod

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8050

CMD ["gunicorn", "dashboard.app:server", "--bind", "0.0.0.0:8050"]
