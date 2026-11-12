# WildDeck UNO Bot

Multiplayer UNO for Telegram groups.

- **Phase 01**: Backend foundation (config, database lifecycle, logging, tests).
- **Phase 02**: Pure-Python core UNO game engine.
- **Phase 03**: Advanced UNO mechanics (WDF challenge, stacking, custom scoring, auto-UNO).
- **Phase 04**: Database persistence, snapshot restoration, optimistic concurrency, and game recovery.
- **Phase 05**: Telegram bot integration (Aiogram 3, handlers, inline keyboards, message formatters, permissions).

## Stack
Python 3.12+, Aiogram 3, PostgreSQL 16 + SQLAlchemy 2 (async, asyncpg), Alembic,
Pydantic Settings, pytest + pytest-asyncio, ruff.

## Architecture
```
app/
  main.py           entry point / lifecycle (polling or webhook, graceful shutdown)
  config.py         Pydantic Settings (single source of configuration)
  bot/              Telegram layer only: dispatcher, handlers, keyboards, middlewares, filters
    handlers/       routers for start, help, rules, about, game commands, callbacks, errors
    keyboards/      inline keyboard builders with CallbackData schemas
    formatters/     safe HTML message templates with html.escape()
    filters/        chat type filters (private vs group)
    context.py      TelegramContext extraction and sanitization
  engine/           pure-Python game engine - zero dependencies on database or Telegram
  services/         application services (GamePersistenceService, TelegramGameService)
  repositories/     database query layer (GameRepository)
  database/         Base, async Database session/engine, models/ (GameRecord), exceptions
  themes/           card theme registry
  scheduler/        timers/background jobs
  utils/            logging with secret redaction
migrations/         Alembic async migrations
tests/              pytest test suite (bot, engine, config, database, persistence)
```

Dependencies flow one way:
`bot -> services -> (engine, repositories) -> database`.

The UNO engine remains completely decoupled from PostgreSQL, SQLAlchemy, Redis, and Telegram.

## Telegram Bot Integration (Phase 05)

### Commands
| Command | Scope | Description |
|---|---|---|
| `/start` | Private / Groups | Bot introduction and interactive navigation menu |
| `/help` | All chats | Guide to all available commands and features |
| `/rules` | All chats | Official UNO rules and special card mechanics |
| `/about` | All chats | Technical information and version status |
| `/newgame` | Groups / Private | Initialize a new UNO game session or group lobby |
| `/status` | All chats | Real-time game status, turn indicators, and player counts |
| `/cancel` | All chats | Cancel an ongoing game (creator or group admin only) |

### Key Features
- **Strict Separation of Concerns**: Handlers delegate all logic to `TelegramGameService`, preserving pure-Python engine neutrality.
- **Duplicate Prevention**: Chats can only host one active or pending game at a time; new game attempts offer direct shortcuts to the active session.
- **Role-Based Authorization**: Games can only be cancelled by the player who initiated them or group administrators via Telegram's chat permissions API.
- **HTML Injection Protection**: All dynamic user-generated text is sanitized through `html.escape()` prior to rendering.
- **Interactive Inline Keyboards**: Structured callbacks (`MenuAction`, `GameAction`) provide rapid navigation with automatic query acknowledgment and graceful handling of expired game sessions.

## Database & Persistence (Phase 04)

### Database Model: `games`
The persistence layer stores snapshots in a single `games` table:
- `id`: Internal autoincrement primary key (`Integer`).
- `game_id`: Unique public game identifier (`String(64)`, indexed, unique).
- `status`: Game lifecycle state (`String(32)`, indexed, values: `created`, `active`, `completed`, `cancelled`).
- `version`: Monotonically increasing version number (`Integer`, default `1`) for optimistic concurrency control.
- `state`: Deterministic JSON snapshot (`JSONB` on PostgreSQL, `JSON` on SQLite).
- `winner_id`: Winner user ID (`Integer`, nullable, indexed).
- `created_at`: Timezone-aware UTC creation timestamp (`DateTime(timezone=True)`).
- `updated_at`: Timezone-aware UTC update timestamp (`DateTime(timezone=True)`).
- `started_at`: Timestamp when the game transitioned to `active`.
- `completed_at`: Timestamp when the game transitioned to `completed` or `cancelled`.

### Concurrency Protection
Optimistic locking is enforced on every game state save:
- Updates check `WHERE game_id = :game_id AND version = :current_version`.
- Successful updates increment `version` to `current_version + 1`.
- Outdated updates fail with `VersionConflictError` instead of silently overwriting newer state.
- Updates to completed or cancelled games raise `InvalidLifecycleTransitionError`.

## Native Development Setup

All development, testing, database migrations, and execution run natively on the host machine.

### 1. Prerequisites
- Python 3.12+ (64-bit)
- PostgreSQL 16+ installed natively
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### 2. Python Environment Setup

In PowerShell:
```powershell
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install requirements
python -m pip install -r requirements-dev.txt
```

On Linux/macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

### 3. Native PostgreSQL Setup

Configure your connection string in `.env`:
```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/uno
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

Run database migrations:
```powershell
alembic upgrade head
```

### 4. Running the Bot
```powershell
python -m app.main
```

### 5. Running Tests and Linter
```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```
