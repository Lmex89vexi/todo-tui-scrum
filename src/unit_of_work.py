"""Unit of Work pattern implementation for transaction management.

Provides abstraction for database transactions and repository access:
- AbstractUnitOfWork: Protocol defining transaction interface
- SqlAlchemyUnitOfWork: Concrete implementation using SQLAlchemy ORM
- LockService: Distributed lock for preventing concurrent writes
- DbState: Tracks database state (dirty flag, etc)

Usage:
    with uow_factory() as uow:
        todos = uow.todos.list()
        # Auto-commit on exit if no exception, else rollback
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from datetime import datetime

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from database import get_session_factory
from models import DbLock
from repositories import SqlAlchemyTodoRepository, TodoRepository


@dataclass
class DbState:
    """Database state tracking for Unit of Work.

    Attributes:
        dirty: Flag indicating if database has pending uncommitted changes.
    """

    dirty: bool = False


class AbstractUnitOfWork:
    """Abstract base for Unit of Work pattern.

    Defines the contract for transaction management and repository access.
    Enables context manager protocol (__enter__, __exit__) for automatic
    commit-on-success or rollback-on-error semantics.

    Attributes:
        todos: TodoRepository instance for accessing todo data.
    """

    todos: TodoRepository

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc, tb):
        """Exit context manager.

        Commits if no exception occurred; rolls back otherwise.
        """
        if exc:
            self.rollback()
        else:
            self.commit()

    def commit(self) -> None:
        """Commit pending transaction changes.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError

    def rollback(self) -> None:
        """Rollback pending transaction changes.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    """SQLAlchemy implementation of Unit of Work pattern.

    Single Responsibility: manage SQLAlchemy session lifecycle and coordinate
    repository access within a single transaction.

    Lifecycle:
      - __enter__: Create session and initialize repositories
      - Code block: Execute queries/commands
      - __exit__: Commit or rollback based on exception state

    All exceptions during commit trigger automatic rollback and are re-raised.
    """

    def __init__(self) -> None:
        """Initialize Unit of Work factory.

        Session creation is deferred to __enter__ to ensure proper lifecycle.
        """
        self._session_factory = get_session_factory()
        self._session = None
        self.todos = None

    def __enter__(self):
        """Enter context manager: create session and repositories.

        Returns:
            Self (AbstractUnitOfWork instance).
        """
        self._session = self._session_factory()
        self.todos = SqlAlchemyTodoRepository(self._session)
        logger.debug("Unit of work started")
        return super().__enter__()

    def __exit__(self, exc_type, exc, tb):
        """Exit context manager: close session regardless of outcome.

        Args:
            exc_type: Exception type if exception occurred, None otherwise.
            exc: Exception instance if exception occurred.
            tb: Traceback if exception occurred.

        Returns:
            Result of parent __exit__ (commit/rollback logic).
        """
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            if self._session is not None:
                self._session.close()
                logger.debug("Unit of work closed")

    def commit(self) -> None:
        """Commit pending changes to database.

        If session does not exist, silently returns (idempotent).
        On SQLAlchemy error, rolls back and re-raises.

        Raises:
            SQLAlchemyError: If commit fails and cannot be retried.
        """
        if self._session is None:
            return
        try:
            self._session.commit()
            logger.debug("Unit of work committed")
        except SQLAlchemyError:
            self._session.rollback()
            logger.exception("Commit failed, rolled back")
            raise

    def rollback(self) -> None:
        """Rollback pending changes.

        If session does not exist, silently returns (idempotent).
        """
        if self._session is None:
            return
        self._session.rollback()
        logger.debug("Unit of work rolled back")


class LockService:
    """Distributed lock service for preventing concurrent database writes.

    Implements a simple distributed lock using a database table.
    One application instance acquires the lock on startup; others must wait or fail.

    Single Responsibility: manage database lock acquisition and release.

    Lock record (DbLock table, id=1):
      - is_locked: 0 = unlocked, 1 = locked
      - locked_by: hostname:pid of lock holder
      - locked_at: timestamp when lock was acquired
    """

    def __init__(self, uow_factory=None) -> None:
        """Initialize lock service.

        Args:
            uow_factory: Unit of Work factory callable. If None, uses default.
        """
        if uow_factory is None:
            from factory import get_unit_of_work_factory
            uow_factory = get_unit_of_work_factory()
        self._uow_factory = uow_factory

    def acquire(self, force: bool = False) -> None:
        """Acquire database lock.

        Creates lock record if not exists. If already locked and force=False,
        raises RuntimeError. If force=True, forcefully acquires lock.

        Args:
            force: If True, override existing lock. If False, fail on locked DB.

        Raises:
            RuntimeError: If database already locked (force=False).
        """
        with self._uow_factory() as uow:
            lock = uow._session.get(DbLock, 1)
            if lock is None:
                lock = DbLock(id=1)
                uow._session.add(lock)
                uow._session.flush()

            if lock.is_locked and not force:
                logger.error("Database is locked by {owner}", owner=lock.locked_by)
                raise RuntimeError(
                    "Database is locked. Use --force-unlock to override."
                )

            lock.is_locked = 1
            lock.locked_by = self._lock_owner()
            lock.locked_at = datetime.utcnow()
            logger.debug("Lock acquired by {owner}", owner=lock.locked_by)

    def release(self) -> None:
        """Release database lock.

        Idempotent: if no lock record exists, silently returns.
        """
        with self._uow_factory() as uow:
            lock = uow._session.get(DbLock, 1)
            if lock is None:
                return
            lock.is_locked = 0
            lock.locked_by = ""
            lock.locked_at = None
            logger.debug("Lock released")

    @staticmethod
    def _lock_owner() -> str:
        """Generate lock owner identifier.

        Combines hostname and process ID to uniquely identify lock holder
        across multiple machines and processes.

        Returns:
            Lock owner string (format: 'hostname:pid').
        """
        return f"{socket.gethostname()}:{os.getpid()}"
