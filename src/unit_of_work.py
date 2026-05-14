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
    dirty: bool = False


class AbstractUnitOfWork:
    todos: TodoRepository

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc:
            self.rollback()
        else:
            self.commit()

    def commit(self) -> None:
        raise NotImplementedError

    def rollback(self) -> None:
        raise NotImplementedError


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    def __init__(self) -> None:
        self._session_factory = get_session_factory()
        self._session = None
        self.todos = None

    def __enter__(self):
        self._session = self._session_factory()
        self.todos = SqlAlchemyTodoRepository(self._session)
        logger.debug("Unit of work started")
        return super().__enter__()

    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            if self._session is not None:
                self._session.close()
                logger.debug("Unit of work closed")

    def commit(self) -> None:
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
        if self._session is None:
            return
        self._session.rollback()
        logger.debug("Unit of work rolled back")


class LockService:
    def __init__(self, uow_factory=SqlAlchemyUnitOfWork) -> None:
        self._uow_factory = uow_factory

    def acquire(self, force: bool = False) -> None:
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
        return f"{socket.gethostname()}:{os.getpid()}"
