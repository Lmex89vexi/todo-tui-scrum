"""Factory pattern implementation for object creation.

Provides abstraction for creating repositories and unit-of-work instances.
Enables Dependency Inversion: business logic depends on abstractions (factories),
not concrete implementations.

Benefits:
  - Swap implementations without modifying client code
  - Single point of change for construction logic
  - Supports testing with mock/stub implementations

Usage:
    factory = get_unit_of_work_factory()
    with factory() as uow:
        todos = uow.todos.list()
"""

from __future__ import annotations

from typing import Protocol

from database import get_session_factory
from repositories import SqlAlchemyTodoRepository, TodoRepository
from unit_of_work import AbstractUnitOfWork, SqlAlchemyUnitOfWork


class UnitOfWorkFactory(Protocol):
    """Protocol defining Unit of Work factory interface.

    Abstraction for creating UnitOfWork instances.
    Enables Dependency Inversion: decouple business logic from concrete
    implementations. Supports swapping SQLAlchemy, MongoDB, or test backends.
    """

    def __call__(self) -> AbstractUnitOfWork:
        """Create and return a new UnitOfWork instance.

        Returns:
            AbstractUnitOfWork instance ready for use in 'with' block.
        """
        ...


class RepositoryFactory(Protocol):
    """Protocol defining Repository factory interface.

    Abstraction for creating Repository instances.
    Enables Dependency Inversion: decouple business logic from persistence
    backends (SQLAlchemy, MongoDB, in-memory, etc).
    """

    def create_todo_repository(self, session) -> TodoRepository:
        """Create and return a new TodoRepository instance.

        Args:
            session: Backend session/connection object (SQLAlchemy, etc).

        Returns:
            TodoRepository instance implementing the persistence interface.
        """
        ...


class SqlAlchemyRepositoryFactory:
    """Concrete factory for SQLAlchemy-based repositories.

    Single Responsibility: instantiate SQLAlchemy repository implementations.
    All repositories are bound to a specific SQLAlchemy session.

    To add new repositories (e.g., TagRepository):
      1. Define protocol in repositories.py
      2. Implement concrete class
      3. Add create_* method to this factory
    """

    def create_todo_repository(self, session) -> TodoRepository:
        """Create a SqlAlchemyTodoRepository bound to the given session.

        Args:
            session: Active SQLAlchemy Session instance.

        Returns:
            SqlAlchemyTodoRepository configured with the session.
        """
        return SqlAlchemyTodoRepository(session)


class DefaultUnitOfWorkFactory:
    """Default factory for creating SqlAlchemy UnitOfWork instances.

    Single Responsibility: create fully initialized UnitOfWork instances.
    Can be replaced with alternative implementations:
      - TestUnitOfWorkFactory (for unit tests)
      - MongoDbUnitOfWorkFactory (for MongoDB backend)
      - InMemoryUnitOfWorkFactory (for integration tests)

    No state; all methods are static for clarity.
    """

    @staticmethod
    def create() -> AbstractUnitOfWork:
        """Create a new SqlAlchemyUnitOfWork instance.

        Returns:
            SqlAlchemyUnitOfWork ready for use in context manager.
        """
        return SqlAlchemyUnitOfWork()


def get_unit_of_work_factory() -> UnitOfWorkFactory:
    """Get the configured Unit of Work factory.

    Returns the default factory method. Extend this function to support
    runtime factory selection (e.g., based on environment variables or config).

    Future: Could use dependency injection container:
        # from some_di_container import get_factory
        # return get_factory(UnitOfWorkFactory)

    Returns:
        UnitOfWorkFactory callable that creates AbstractUnitOfWork instances.
    """
    return DefaultUnitOfWorkFactory.create
