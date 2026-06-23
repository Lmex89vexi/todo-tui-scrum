# AGENTS

## How to use

1. Create a venv and install dependencies:
   - `uv venv`
   - `uv sync`
2. Run the TUI:
   - `uv run todo`
3. Use the app:
   - Add tasks by typing in the new task input (shown with `i` or `a`).
   - Filter with `/` and queries like `status:pending`, `tag:work`, `#work`, or `deleted:true`.
   - Toggle done with `x`, cancel with `c`, restore cancelled tasks with `u`, delete with `d`.

## Runtime notes

- DB URL: default `sqlite:///./todo.db`, override with `TODO_DB_URL` (Postgres uses `postgresql+psycopg://...`).
- Schema is created at startup via `Base.metadata.create_all(engine)` (no Alembic).
- Startup always acquires a DB lock; if no writes occurred, the lock is released on exit; use `--force-unlock` to override.
- Logs: loguru writes to `pytodo.log`; configure with `TODO_LOG_LEVEL`, `TODO_LOG_FILE`, `TODO_LOG_ROTATION`, `TODO_LOG_RETENTION`.

## Filters

- Filter syntax: `status:pending`, `status:completed`, `status:cancelled`, `stat:completed`, `s:done`, `tag:work`, `t:work`, `#work`, `deleted:true`, `deleted:false`, `deleted:all`, plain text matches task.
- Default tag for existing tasks: `TODO_DEFAULT_TASK_TAGS` (default `work`); set empty to disable; runs once via `app_settings` marker; re-run with `--apply-default-tags`.
- Filter defaults: `TODO_FILTER_DEFAULT_TAGS` overrides default tags for filtering; `TODO_FILTER_ALIASES` adds alias pairs like `status=st;tag=label`.
