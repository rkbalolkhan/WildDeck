# WildDeck UNO Bot

Multiplayer UNO for Telegram groups.

- **Phase 01**: Backend foundation (config, database lifecycle, logging, tests).
- **Phase 02**: Pure-Python core UNO game engine.
- **Phase 03**: Advanced UNO mechanics (WDF challenge, stacking, custom scoring, auto-UNO).
- **Phase 04**: Database persistence, snapshot restoration, optimistic concurrency, and game recovery.

## Stack
Python 3.12+, aiogram 3, PostgreSQL 16 + SQLAlchemy 2 (async, asyncpg), Alembic,
Pydantic Settings, pytest + pytest-asyncio, ruff.

## Architecture
```
app/
  main.py           entry point / lifecycle (polling or webhook, graceful shutdown)
  config.py         Pydantic Settings (single source of configuration)
  bot/              Telegram layer only: dispatcher, handlers, keyboards, middlewares, filters
  engine/           pure-Python game engine - zero dependencies on database or Telegram
  services/         use-cases orchestrating engine + repositories (e.g. GamePersistenceService)
  repositories/     database query layer (e.g. GameRepository)
  database/         Base, async Database session/engine, models/ (GameRecord), exceptions
  themes/           card theme registry
  scheduler/        timers/background jobs
  utils/            logging with secret redaction
migrations/         Alembic async migrations
tests/              pytest test suite (engine, config, database, persistence)
```

Dependencies flow one way:
`bot -> services -> (engine, repositories) -> database`.

The UNO engine remains completely decoupled from PostgreSQL, SQLAlchemy, Redis, and Telegram.

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

### Game Restoration & Recovery
- `GamePersistenceService.load_game(game_id)` loads any game record and deserializes it into a fully validated engine `Game` instance.
- `GamePersistenceService.restore_game(game_id)` verifies the game is `ACTIVE` and ready for play.
- Advanced mechanics (pending draw penalties, stacked counts, UNO windows, WDF challenge snapshots and hidden cards, round scores, match scores) are fully preserved.
- `GamePersistenceService.recover_active_games()` iterates over all active games after an application restart, restoring valid games and logging corrupted games with structured metadata (`game_id`, `error_category`) without crashing or leaking sensitive hand contents.

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

# Upgrade pip and install package in editable mode with development dependencies
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

On Linux/macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 3. Native PostgreSQL Setup

#### Installation
- **Windows**: Download the official installer from [postgresql.org](https://www.postgresql.org/download/windows/) or install via winget:
  ```powershell
  winget install PostgreSQL.PostgreSQL
  ```
- **macOS**: `brew install postgresql@16 && brew services start postgresql@16`
- **Linux (Ubuntu/Debian)**: `sudo apt install postgresql postgresql-contrib && sudo systemctl start postgresql`

#### Windows Service Management
To check whether the PostgreSQL Windows service is running, find the installed service name:
```powershell
# Discover the PostgreSQL service name
Get-Service *postgres*

# Start the service if not running (substitute your service name, e.g. postgresql-x64-16)
Start-Service postgresql*

# Verify service status
Get-Service postgresql*
```

#### Database Creation
Create the development and test databases using `psql` or `createdb`:
```powershell
# Using psql (enter the superuser password when prompted)
psql -U postgres -c "CREATE DATABASE wilddeck;"
psql -U postgres -c "CREATE DATABASE wilddeck_test;"
```

#### Configure Environment Variables
Copy `.env.example` to `.env` and configure your credentials:
```powershell
Copy-Item .env.example .env
```

Edit `.env`:
```env
BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ_01234567
BOT_MODE=polling

DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/wilddeck
TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/wilddeck_test
```

### 4. Database Migrations

Apply database migrations to native PostgreSQL:
```powershell
# Run online migrations
python -m alembic upgrade head

# Or check SQL output offline without connecting
python -m alembic upgrade head --sql

# Roll back the most recent migration
python -m alembic downgrade -1
```

### 5. Running the Application

Start the bot entry point natively:
```powershell
python -m app.main
```

### 6. Tests and Quality Checks

Run the test suite and linters:
```powershell
# Run all tests
python -m pytest -q

# Run Ruff linter and code formatter checks
python -m ruff check .
python -m ruff format --check .
```

### 7. PostgreSQL Integration Testing

- By default, unit tests execute against an in-memory SQLite database using `StaticPool` and JSON emulation, requiring zero external infrastructure.
- To execute PostgreSQL integration tests against your local database:
  1. Ensure your local PostgreSQL service is running.
  2. Set `TEST_DATABASE_URL` in `.env` or in the environment:
     ```powershell
     $env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/wilddeck_test"
     python -m pytest tests/persistence -v
     ```
  3. Integration tests verify native PostgreSQL `JSONB` storage, indexing, and transactional concurrency on `wilddeck_test`. The development database (`wilddeck`) is never dropped or touched by test runs.

## Redis Note
Redis is optional in WildDeck. Persistent game records, snapshot storage, and optimistic concurrency are stored in PostgreSQL as the single source of truth. Redis is not required for native local development or running tests.

## Service Layer Usage Example

```python
from app.database.session import Database
from app.engine.game import Game
from app.engine.player import Player
from app.services.persistence import GamePersistenceService

db = Database("postgresql+asyncpg://postgres:password@localhost:5432/wilddeck")
service = GamePersistenceService(db)

# 1. Create a game and persist it
game = Game.new([Player(1, "Alice"), Player(2, "Bob")])
record = await service.create_game(game)
print(f"Created game {record.game_id} at version {record.version}")

# 2. Play turns and save state with concurrency check
game.draw_card(game.current_player_id)
updated = await service.save_game(game, current_version=record.version)

# 3. Restore an active game after restart
restored = await service.restore_game(game.game_id)
assert restored.game.current_player_id == game.current_player_id

# 4. Recover all active games at startup
report = await service.recover_active_games()
print(f"Recovered {len(report.restored)} active games, {len(report.failed)} failed")
```

## Known Limitations
- Telegram user profiles, avatars, and Telegram-specific chat state are deferred to Phase 05.
- Real-time matchmaking and ephemeral group lobby management will be introduced in subsequent phases.
