from __future__ import annotations

import os

from loguru import logger
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from models import Base


DEFAULT_DB_URL = "sqlite:///./todo.db"


def get_database_url() -> str:
    return os.getenv("TODO_DB_URL", DEFAULT_DB_URL)


def get_engine():
    return create_engine(get_database_url(), future=True)


def init_db(engine) -> None:
    logger.debug("Initializing database schema")
    Base.metadata.create_all(engine)
    _ensure_todo_soft_delete_column(engine)


def _ensure_todo_soft_delete_column(engine) -> None:
    inspector = inspect(engine)
    if "todos" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("todos")}
    if "is_deleted" in columns:
        return
    logger.debug("Adding missing todos.is_deleted column")
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE todos ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0"
            )
        )


def get_session_factory():
    engine = get_engine()
    init_db(engine)
    logger.debug("Session factory ready")
    return sessionmaker(bind=engine, future=True)
