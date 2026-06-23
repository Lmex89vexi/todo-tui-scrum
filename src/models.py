"""SQLAlchemy ORM models for todo-tui-scrum.

Defines data models for persisting todos, database locks, and application settings.
Each model represents a single domain entity with clear responsibility.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base class.

    Common base for all ORM models, providing metadata registry and
    reflection capabilities required by SQLAlchemy's type annotation system.
    """

    pass


class Todo(Base):
    """Domain model representing a single todo task.

    Single Responsibility: encapsulates todo data and state transitions.
    Status transitions: pending → completed or pending → cancelled.
    Soft deletes: is_deleted flag preserves audit trail.

    Attributes:
        id: Unique primary key, auto-incremented on insert.
        task: Task description (max 500 chars).
        status: One of pending, completed, cancelled.
        tags: Comma-separated tag list (e.g., 'work,urgent').
        due_date: Optional target completion date.
        is_deleted: Soft delete flag; False = active, True = deleted.
        created_at: Timestamp when task was created (UTC).
        completed_at: Timestamp when task transitioned to completed.
    """

    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    tags: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DbLock(Base):
    """Distributed lock for preventing concurrent database writes.

    Single Responsibility: tracks database lock state and ownership.
    Ensures only one application instance can write to the database at a time.

    Attributes:
        id: Primary key (always 1, singleton row).
        is_locked: Lock state; 0 = unlocked, 1 = locked.
        locked_by: Hostname or process identifier holding the lock.
        locked_at: Timestamp when lock was acquired (UTC).
    """

    __tablename__ = "db_lock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    is_locked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_by: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AppSetting(Base):
    """Application configuration and state flags.

    Single Responsibility: stores application metadata and one-time initialization flags.
    Used to track events like 'default_tags_applied' to prevent re-running migrations.

    Attributes:
        key: Configuration key identifier (primary key).
        value: Configuration value as string (max 500 chars).
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False, default="")
