"""Database initialization and session management.

Handles:
  - Engine creation from connection URL
  - Schema creation and migrations (via ALTER TABLE)
  - Session factory setup for SQLAlchemy ORM

Environment variables:
  - TODO_DB_URL: Database connection URL (default: sqlite:///./todo.db)

Migration strategy (NO Alembic):
  Automatically adds missing columns to existing tables via ALTER TABLE.
  Supports adding columns if they don't exist (idempotent).
"""

from __future__ import annotations

import os

from loguru import logger
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from models import Base


DEFAULT_DB_URL = "sqlite:///./todo.db"
"""Default database connection URL if TODO_DB_URL not set."""


def get_database_url() -> str:
    """Get database connection URL from environment or use default.

    Returns:
        Database URL string (SQLite or PostgreSQL connection string).
    """
    return os.getenv("TODO_DB_URL", DEFAULT_DB_URL)


def get_engine():
    """Create SQLAlchemy engine from configured database URL.

    Uses future=True flag for SQLAlchemy 2.0 API compatibility.

    Returns:
        SQLAlchemy Engine instance configured with database URL.
    """
    return create_engine(get_database_url(), future=True)


def init_db(engine) -> None:
    """Initialize database schema and apply migrations.

    Creates tables defined in Base.metadata if they don't exist.
    Then applies migration logic to add any missing columns:
      - todos.is_deleted (soft delete flag)
      - todos.created_at (creation timestamp)
      - todos.completed_at (completion timestamp)

    Args:
        engine: SQLAlchemy Engine instance to use for schema creation.
    """
    logger.debug("Initializing database schema")
    Base.metadata.create_all(engine)
    _ensure_todo_soft_delete_column(engine)
    _ensure_todo_created_at_column(engine)
    _ensure_todo_completed_at_column(engine)


def _ensure_todo_soft_delete_column(engine) -> None:
    """Ensure todos table has is_deleted column (migration).

    Adds is_deleted column if it doesn't exist. Idempotent.
    Existing rows get default value of 0 (not deleted).

    Args:
        engine: SQLAlchemy Engine instance.
    """
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


def _ensure_todo_created_at_column(engine) -> None:
    """Ensure todos table has created_at column (migration).

    Adds created_at column if it doesn't exist. Idempotent.
    Existing rows get NULL value for created_at.

    Args:
        engine: SQLAlchemy Engine instance.
    """
    inspector = inspect(engine)
    if "todos" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("todos")}
    if "created_at" in columns:
        return
    logger.debug("Adding missing todos.created_at column")
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE todos ADD COLUMN created_at DATETIME")
        )


def _ensure_todo_completed_at_column(engine) -> None:
    """Ensure todos table has completed_at column (migration).

    Adds completed_at column if it doesn't exist. Idempotent.
    Existing rows get NULL value for completed_at.

    Args:
        engine: SQLAlchemy Engine instance.
    """
    inspector = inspect(engine)
    if "todos" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("todos")}
    if "completed_at" in columns:
        return
    logger.debug("Adding missing todos.completed_at column")
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE todos ADD COLUMN completed_at DATETIME")
        )


def get_session_factory():
    """Create and configure SQLAlchemy session factory.

    Initializes database schema and returns a sessionmaker callable.
    Uses future=True for 2.0 API compatibility.

    Returns:
        sessionmaker instance configured to create new sessions on call.
    """
    engine = get_engine()
    init_db(engine)
    logger.debug("Session factory ready")
    return sessionmaker(bind=engine, future=True)
