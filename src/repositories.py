from __future__ import annotations

import os
from typing import Protocol

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from models import AppSetting, Todo


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

    def _load_filter_aliases(self) -> dict[str, set[str]]:
        aliases: dict[str, set[str]] = {
            "status": {"status", "stat", "s"},
            "tag": {"tag", "t"},
        }
        raw = os.getenv("TODO_FILTER_ALIASES", "").strip()
        if not raw:
            return aliases
        for group in raw.split(";"):
            group = group.strip()
            if not group or "=" not in group:
                continue
            key, values = group.split("=", 1)
            key = key.strip()
            if key not in aliases:
                continue
            for alias in values.split(","):
                alias = alias.strip()
                if alias:
                    aliases[key].add(alias)
        return aliases

    def _load_default_tags(self) -> list[str]:
        raw = os.getenv("TODO_FILTER_DEFAULT_TAGS", "").strip()
        if not raw:
            raw = os.getenv("TODO_DEFAULT_TASK_TAGS", "work").strip()
        if not raw:
            return []
        tags = [tag.strip() for tag in raw.split(",")]
        return [tag for tag in tags if tag]

    def _normalize_status(self, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"done", "complete", "completed", "c"}:
            return "completed"
        if normalized in {"cancelled", "canceled", "cancel", "cancelado"}:
            return "cancelled"
        if normalized in {"pending", "todo", "p"}:
            return "pending"
        return normalized

    def _parse_filter_query(
        self, query: str
    ) -> tuple[list[str], list[str], list[str]]:
        aliases = self._load_filter_aliases()
        status_values: list[str] = []
        tag_values: list[str] = self._load_default_tags()
        text_terms: list[str] = []

        for token in query.split():
            if token.startswith("#") and len(token) > 1:
                tag_values = []
                tag_values.append(token[1:])
                continue
            if ":" in token:
                raw_key, raw_value = token.split(":", 1)
                key = raw_key.strip().lower()
                value = raw_value.strip()
                if not value:
                    continue
                if key in aliases["status"]:
                    for item in value.split(","):
                        item = item.strip()
                        if item:
                            status_values.append(self._normalize_status(item))
                    continue
                if key in aliases["tag"]:
                    tag_values = []
                    for item in value.split(","):
                        item = item.strip()
                        if item:
                            tag_values.append(item)
                    continue
            text_terms.append(token)

        return status_values, tag_values, text_terms

    def list(self, query: str | None = None) -> list[Todo]:
        statement = select(Todo).where(Todo.is_deleted.is_(False))
        if query:
            status_values, tag_values, text_terms = self._parse_filter_query(query)
            conditions = []
            if status_values:
                conditions.append(Todo.status.in_(status_values))
            if tag_values:
                for tag in tag_values:
                    tag_like = tag.replace("%", "\\%")
                    conditions.append(
                        or_(
                            Todo.tags == tag_like,
                            Todo.tags.ilike(f"{tag_like},%"),
                            Todo.tags.ilike(f"%,{tag_like},%"),
                            Todo.tags.ilike(f"%,{tag_like}"),
                        )
                    )
            if text_terms:
                for term in text_terms:
                    like = f"%{term}%"
                    conditions.append(Todo.task.ilike(like))
            if conditions:
                statement = statement.where(and_(*conditions))
        return list(self._session.scalars(statement).all())

    def apply_default_tags_to_untagged(self, default_tags: list[str]) -> int:
        if not default_tags:
            return 0
        tags_value = ",".join(default_tags)
        statement = (
            update(Todo)
            .where(
                and_(
                    Todo.is_deleted.is_(False),
                    or_(Todo.tags == "", Todo.tags.is_(None)),
                )
            )
            .values(tags=tags_value)
        )
        result = self._session.execute(statement)
        return int(result.rowcount or 0)

    def get_setting(self, key: str) -> str | None:
        setting = self._session.get(AppSetting, key)
        if setting is None:
            return None
        return setting.value

    def set_setting(self, key: str, value: str) -> None:
        setting = self._session.get(AppSetting, key)
        if setting is None:
            self._session.add(AppSetting(key=key, value=value))
        else:
            setting.value = value

    def get(self, todo_id: int) -> Todo | None:
        return self._session.get(Todo, todo_id)

    def add(self, todo: Todo) -> None:
        self._session.add(todo)

    def remove(self, todo: Todo) -> None:
        todo.is_deleted = True
