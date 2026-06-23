# PyTodo-TUI

PyTodo-TUI is a keyboard-first, single-user task manager with a Vim-style TUI.
It uses SQLite by default and supports PostgreSQL via `TODO_DB_URL`.

For agent-specific workflow hints, see `AGENTS.md`.

## Setup

```bash
uv venv
uv sync
```

### Alternative setup with pip

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requeriments.pip
```

## Run

```bash
uv run todo
```

## Install as Global Command (Linux)

```bash
uv tool install -e .
```

This installs the `todo` command in your user environment. If the command is
not found, ensure `~/.local/bin` is in your `PATH`.

Uninstall:

```bash
uv tool uninstall pytodo-tui
```

System-wide (requires sudo):

```bash
sudo uv tool install -e .
```

### Install/Uninstall Scripts

```bash
./scripts/install.sh
./scripts/uninstall.sh
```

System-wide:

```bash
./scripts/install.sh --system
./scripts/uninstall.sh --system
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

## Filtering

Open the filter with `/`, type a query, and press Enter.

- Status: `status:pending`, `status:completed`, `status:cancelled`
- Short aliases: `stat:completed`, `s:done`
- Tags: `tag:work`, `t:work`, `#work`
- Deleted: `deleted:true`, `deleted:false`, `deleted:all`
- Multiple values: `status:pending,completed`, `tag:work,home`
- Plain text matches task content

### Filter Configuration

- `TODO_FILTER_DEFAULT_TAGS` sets default tags for filtering (comma-separated)
- `TODO_FILTER_ALIASES` adds alias pairs like `status=st,stt;tag=label,l`

## Default Tags

Existing tasks with empty tags get default tags applied once at startup.

- `TODO_DEFAULT_TASK_TAGS` (default: `work`)
- Set `TODO_DEFAULT_TASK_TAGS=""` to disable the one-time update
- Use `--apply-default-tags` to re-run the update later

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
