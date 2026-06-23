"""Repository layer for todo persistence.

Implements the Repository Pattern and Dependency Inversion:
- TodoRepository: Protocol defining the persistence interface.
- SqlAlchemyTodoRepository: Concrete implementation for SQLAlchemy ORM.

Filter syntax supports:
  - status: 'pending', 'completed', 'cancelled' (aliases: s, stat)
  - tag: comma-separated tags (aliases: t, #tag)
  - deleted: true/false/all (aliases: d, del)
  - text: full-text search on task description

Example: 'status:pending tag:work status:pending hello world'
"""

from __future__ import annotations

import os
from typing import Protocol

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from models import AppSetting, Todo


class TodoRepository(Protocol):
    """Protocol defining the todo persistence interface.

    Abstraction for Dependency Inversion: business logic depends on this
    interface, not concrete implementations (SQLAlchemy, MongoDB, etc).
    Any implementation must satisfy all methods without modification to clients.
    """

    def list(self, query: str | None = None) -> list[Todo]:
        """Retrieve todos matching the query filter.

        Args:
            query: Optional filter string (e.g., 'status:pending #work hello').
                   None or empty defaults to active todos only.

        Returns:
            List of Todo instances matching filter criteria.
        """
        ...

    def get(self, todo_id: int) -> Todo | None:
        """Retrieve a single todo by ID.

        Args:
            todo_id: Primary key of the todo.

        Returns:
            Todo instance if found, None otherwise.
        """
        ...

    def add(self, todo: Todo) -> None:
        """Add a new todo to the repository.

        Args:
            todo: Todo instance to persist. ID will be auto-generated on commit.
        """
        ...

    def remove(self, todo: Todo) -> None:
        """Soft-delete a todo by setting is_deleted flag.

        Args:
            todo: Todo instance to mark as deleted.
        """
        ...


class SqlAlchemyTodoRepository:
    """Concrete repository implementation using SQLAlchemy ORM.

    Single Responsibility: encapsulates all SQLAlchemy query logic and filter parsing.
    Responsibility separation:
      - Filter parsing: _parse_filter_query(), _normalize_status()
      - Alias/config loading: _load_filter_aliases(), _load_default_tags()
      - CRUD operations: list(), get(), add(), remove()
      - Settings management: get_setting(), set_setting()
      - Batch operations: apply_default_tags_to_untagged()

    Filter Query Examples:
      - 'status:pending' → active pending tasks
      - '#work' → tasks tagged with 'work'
      - 'status:completed,pending' → multiple statuses
      - 'hello world' → full-text search on task description
      - 'deleted:all' → include deleted tasks

    Environment variables:
      - TODO_FILTER_ALIASES: Custom filter aliases (e.g., 'status=st;tag=label')
      - TODO_FILTER_DEFAULT_TAGS: Default tags if none provided
      - TODO_DEFAULT_TASK_TAGS: Default tags when creating tasks
    """

    def __init__(self, session: Session) -> None:
        """Initialize repository with SQLAlchemy session.

        Args:
            session: Active SQLAlchemy Session instance. Caller is responsible
                     for session lifecycle (open/close).
        """
        self._session = session

    def _load_filter_aliases(self) -> dict[str, set[str]]:
        """Load filter key aliases from environment.

        Loads TODO_FILTER_ALIASES environment variable to allow customization
        of filter syntax (e.g., making 'st' an alias for 'status').

        Returns:
            Dictionary mapping canonical filter names to sets of aliases.
        """
        aliases: dict[str, set[str]] = {
            "status": {"status", "stat", "s"},
            "tag": {"tag", "t"},
            "deleted": {"deleted", "del", "d", "is_deleted"},
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
        """Load default tags from environment variables.

        Checks TODO_FILTER_DEFAULT_TAGS first, falls back to TODO_DEFAULT_TASK_TAGS.
        Used when no tags are explicitly provided in filter queries.

        Returns:
            List of default tag strings (empty list if none configured).
        """
        raw = os.getenv("TODO_FILTER_DEFAULT_TAGS", "").strip()
        if not raw:
            raw = os.getenv("TODO_DEFAULT_TASK_TAGS", "work").strip()
        if not raw:
            return []
        tags = [tag.strip() for tag in raw.split(",")]
        return [tag for tag in tags if tag]

    def _normalize_status(self, value: str) -> str:
        """Normalize status input to canonical form.

        Maps user-friendly status names (done, cancel, complete) to canonical
        database values (completed, cancelled, pending).

        Args:
            value: Raw status input from filter query.

        Returns:
            Normalized status: 'pending', 'completed', or 'cancelled'.
        """
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
    ) -> tuple[list[str], list[str], list[str], bool | None, bool]:
        """Parse filter query string into structured components.

        Tokenizes filter query and extracts status, tags, text search terms,
        and soft-delete filter. Syntax:
          - 'status:STATUSES' → filter by status
          - '#TAG' or 'tag:TAGS' → filter by tags
          - 'deleted:true/false/all' → include/exclude deleted
          - plain tokens → text search on task description

        Args:
            query: Raw filter query string (space-separated tokens).

        Returns:
            Tuple of:
              - status_values: list of normalized statuses
              - tag_values: list of tag names
              - text_terms: list of search terms
              - deleted_filter: True/False/None (None = include all)
              - deleted_filter_set: whether deleted filter was explicitly provided
        """
        aliases = self._load_filter_aliases()
        status_values: list[str] = []
        tag_values: list[str] = self._load_default_tags()
        text_terms: list[str] = []
        deleted_filter: bool | None = None
        deleted_filter_set = False

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
                    if value.lower() in {"deleted", "removed", "trash", "trashed"}:
                        deleted_filter = True
                        deleted_filter_set = True
                        continue
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
                if key in aliases["deleted"]:
                    normalized = value.lower()
                    if normalized in {"1", "true", "yes", "y", "only"}:
                        deleted_filter = True
                        deleted_filter_set = True
                    elif normalized in {"0", "false", "no", "n", "active"}:
                        deleted_filter = False
                        deleted_filter_set = True
                    elif normalized in {"all", "any"}:
                        deleted_filter = None
                        deleted_filter_set = True
                    continue
            text_terms.append(token)

        return status_values, tag_values, text_terms, deleted_filter, deleted_filter_set

    def list(self, query: str | None = None) -> list[Todo]:
        """Retrieve todos matching optional filter query.

        If no query provided, returns all active (non-deleted) todos.
        Query supports filter syntax: 'status:pending #work hello world'.

        Args:
            query: Optional filter query string. None defaults to active todos.

        Returns:
            List of Todo instances matching all filter criteria (AND logic).
        """
        statement = select(Todo)
        if query:
            status_values, tag_values, text_terms, deleted_filter, deleted_filter_set = (
                self._parse_filter_query(query)
            )
            conditions = []
            if deleted_filter_set:
                if deleted_filter is True:
                    conditions.append(Todo.is_deleted.is_(True))
                elif deleted_filter is False:
                    conditions.append(Todo.is_deleted.is_(False))
            else:
                conditions.append(Todo.is_deleted.is_(False))
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
        else:
            statement = statement.where(Todo.is_deleted.is_(False))
        return list(self._session.scalars(statement).all())

    def apply_default_tags_to_untagged(self, default_tags: list[str]) -> int:
        """Apply default tags to untagged active todos.

        One-time operation (idempotent via app_settings marker) to assign
        default tags to todos that were created before default tag feature.
        Targets active todos with empty or null tag fields.

        Args:
            default_tags: List of tag strings to assign (joined by comma).

        Returns:
            Count of todos updated.
        """
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
        """Retrieve an application setting value.

        Args:
            key: Setting key identifier.

        Returns:
            Setting value if found, None otherwise.
        """
        setting = self._session.get(AppSetting, key)
        if setting is None:
            return None
        return setting.value

    def set_setting(self, key: str, value: str) -> None:
        """Store or update an application setting.

        Creates new setting if key does not exist, updates existing otherwise.

        Args:
            key: Setting key identifier.
            value: Setting value to store.
        """
        setting = self._session.get(AppSetting, key)
        if setting is None:
            self._session.add(AppSetting(key=key, value=value))
        else:
            setting.value = value

    def get(self, todo_id: int) -> Todo | None:
        """Retrieve a single todo by ID.

        Args:
            todo_id: Primary key of todo to retrieve.

        Returns:
            Todo instance if found, None otherwise.
        """
        return self._session.get(Todo, todo_id)

    def add(self, todo: Todo) -> None:
        """Add a new todo to the session.

        Args:
            todo: Todo instance to persist (ID auto-generated on commit).
        """
        self._session.add(todo)

    def remove(self, todo: Todo) -> None:
        """Soft-delete a todo by setting is_deleted flag.

        Args:
            todo: Todo instance to mark as deleted.
        """
        todo.is_deleted = True
