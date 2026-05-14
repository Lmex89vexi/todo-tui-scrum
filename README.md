# PyTodo-TUI

PyTodo-TUI is a keyboard-first, single-user task manager with a Vim-style TUI.
It uses SQLite by default and supports PostgreSQL via `TODO_DB_URL`.

## Setup

```bash
uv venv
uv sync
```

## Run

```bash
uv run todo
```

## Database

- Default: `sqlite:///./todo.db`
- Override: `TODO_DB_URL="postgresql+psycopg://user:pass@host:5432/db"`

Tables are created automatically on startup via `Base.metadata.create_all(engine)`.

## Locking

- The app always acquires a lock at startup.
- If no DB changes happen, the lock is released on exit.
- Use `--force-unlock` to override an existing lock.

## Input Format

- Tags: `#tag`
- Due date: `@YYYY-MM-DD`

Example:

```
Comprar cafe #compras #urgente @2023-12-31
```

## Logs

Debug logs are written to `pytodo.log` in the project root.

### Log Configuration

- `TODO_LOG_LEVEL` (default: `DEBUG`)
- `TODO_LOG_FILE` (default: `pytodo.log`)
- `TODO_LOG_ROTATION` (default: `1 MB`)
- `TODO_LOG_RETENTION` (default: `7 days`)

Example:

```bash
TODO_LOG_LEVEL=INFO uv run todo
```
