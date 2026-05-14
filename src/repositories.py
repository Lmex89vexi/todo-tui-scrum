from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Todo


class TodoRepository(Protocol):
    def list(self, query: str | None = None) -> list[Todo]:
        ...

    def get(self, todo_id: int) -> Todo | None:
        ...

    def add(self, todo: Todo) -> None:
        ...

    def remove(self, todo: Todo) -> None:
        ...


class SqlAlchemyTodoRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, query: str | None = None) -> list[Todo]:
        statement = select(Todo)
        if query:
            like = f"%{query}%"
            statement = statement.where(Todo.task.ilike(like))
        return list(self._session.scalars(statement).all())

    def get(self, todo_id: int) -> Todo | None:
        return self._session.get(Todo, todo_id)

    def add(self, todo: Todo) -> None:
        self._session.add(todo)

    def remove(self, todo: Todo) -> None:
        self._session.delete(todo)
