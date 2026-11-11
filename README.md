# WildDeck UNO Bot

Multiplayer UNO for Telegram groups.

- **Phase 01**: Backend foundation (config, database lifecycle, logging, Docker, tests).
- **Phase 02**: Pure-Python core UNO game engine.
- **Phase 03**: Advanced UNO mechanics (WDF challenge, stacking, custom scoring, auto-UNO).
- **Phase 04**: Database persistence, snapshot restoration, optimistic concurrency, and game recovery.

## Stack
Python 3.12+, aiogram 3, PostgreSQL 16 + SQLAlchemy 2 (async, asyncpg), Alembic, Redis (optional),
Pydantic Settings, pytest + pytest-asyncio, ruff, Docker Compose.

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

## Prerequisites
Python 3.12+, PostgreSQL 16 (or Docker), a bot token from @BotFather.

## Local Development
```bash
# Setup virtual environment and dependencies
python -m venv .venv
.venv\Scripts\activate  # Windows (or source .venv/bin/activate on Linux/macOS)
pip install -e .

cp .env.example .env    # configure BOT_TOKEN and DATABASE_URL
```

Quick local PostgreSQL:
```bash
docker compose up -d postgres
```

## Migrations
Alembic manages async schema migrations.

```bash
# Run online migrations against target database
python -m alembic upgrade head

# Run offline migrations (output SQL without connecting)
python -m alembic upgrade head --sql

# Rollback last migration
python -m alembic downgrade -1
```

## Running Tests
Run the test suite:
```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

### PostgreSQL Integration Testing
By default, persistence unit tests execute against an in-memory SQLite database using `StaticPool` and JSON emulation.

To run persistence integration tests against a real PostgreSQL instance:
1. Start PostgreSQL (e.g. via `docker compose up -d postgres`).
2. Set the `TEST_DATABASE_URL` environment variable:
```bash
$env:TEST_DATABASE_URL = "postgresql+asyncpg://uno:uno@localhost:5432/uno"  # PowerShell
# or: export TEST_DATABASE_URL="postgresql+asyncpg://uno:uno@localhost:5432/uno"
python -m pytest tests/persistence -v
```

## Service Layer Usage Example

```python
from app.database.session import Database
from app.engine.game import Game
from app.engine.player import Player
from app.services.persistence import GamePersistenceService

db = Database("postgresql+asyncpg://uno:uno@localhost:5432/uno")
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
- Telegram-specific features, user profiles, avatars, and message handlers are deferred to Phase 05.
- Redis-based transient caching and ephemeral lobbies will be integrated alongside persistence in subsequent phases.
