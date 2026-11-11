# UNO Bot

Multiplayer UNO for Telegram groups. **Phase 01**: backend foundation only (config, database,
bot lifecycle, logging, Docker, tests). No gameplay yet.

## Stack
Python 3.12+, aiogram 3, PostgreSQL + SQLAlchemy 2 (async, asyncpg), Alembic, Redis (optional),
Pydantic Settings, pytest + pytest-asyncio, uv, Docker Compose.

## Architecture
```
app/
  main.py        entry point / lifecycle (polling or webhook, graceful shutdown)
  config.py      Pydantic Settings (single source of configuration)
  bot/           Telegram layer only: dispatcher, handlers, keyboards, middlewares, filters
  engine/        pure-Python game engine (Phase 02) - must not import aiogram or SQLAlchemy
  services/      use-cases orchestrating engine + repositories
  repositories/  all database queries
  database/      Base, async engine/session (Database class), models/
  themes/        card theme registry
  scheduler/     timers/background jobs
  utils/         logging with secret redaction
migrations/      Alembic (async env)
```
Dependencies flow one way: `bot -> services -> (engine, repositories) -> database`.
The `Database` object is created in `main` and injected through the dispatcher's workflow data;
there is no global mutable state.

## Prerequisites
Python 3.12+, [uv](https://docs.astral.sh/uv/), PostgreSQL 16 (or Docker), a bot token from @BotFather.

## Local development
```bash
uv sync                      # install deps (incl. dev)
cp .env.example .env         # then set BOT_TOKEN and DATABASE_URL
uv run python -m app.main    # start the bot
```
Quick local database: `docker compose up -d postgres`
(compose exposes PostgreSQL only on the internal network; add a `ports` mapping if you run the bot on the host).

## Environment
| Variable | Notes |
|---|---|
| `BOT_TOKEN` | required |
| `BOT_MODE` | `polling` (default) or `webhook` |
| `BOT_WEBHOOK_URL` / `BOT_WEBHOOK_SECRET` | required for webhook mode (https URL) |
| `BOT_WEBHOOK_HOST` / `BOT_WEBHOOK_PORT` | webhook server bind (default `0.0.0.0:8080`) |
| `DATABASE_URL` | `postgresql+asyncpg://...` (plain `postgresql://` is auto-converted) |
| `REDIS_URL` | optional |
| `LOG_LEVEL` | `DEBUG`..`CRITICAL` (default `INFO`) |
| `ENVIRONMENT` | `development` / `production` / `testing` |

## Docker Compose
```bash
cp .env.example .env
docker compose up --build                 # bot + postgres
docker compose --profile redis up --build # also Redis
```
Inside compose the bot reaches PostgreSQL at `postgres:5432`; `DATABASE_URL` is overridden for you.

## Tests and linting
```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```
Tests need no Telegram credentials or running database.

## Migrations
```bash
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
uv run alembic downgrade -1
```

## Roadmap
1. Foundation (this phase) 2. Game engine 3. Themes/cards 4. DB models and statistics
5. Telegram handlers and gameplay 6. Persistence/recovery, Redis state, scheduler
