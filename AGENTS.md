# AGENTS

- Setup: `uv venv` then `uv sync`.
- Run: `uv run todo` (entrypoint from `pyproject.toml`).
- DB URL: default `sqlite:///./todo.db`, override with `TODO_DB_URL` (Postgres uses `postgresql+psycopg://...`).
- Schema is created at startup via `Base.metadata.create_all(engine)` (no Alembic).
- Startup always acquires a DB lock; if no writes occurred, the lock is released on exit; use `--force-unlock` to override.
- Logs: loguru writes to `pytodo.log`; configure with `TODO_LOG_LEVEL`, `TODO_LOG_FILE`, `TODO_LOG_ROTATION`, `TODO_LOG_RETENTION`.
