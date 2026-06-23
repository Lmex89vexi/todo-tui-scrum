"""Terminal User Interface for todo-tui-scrum.

Textual-based TUI providing interactive todo management:
  - View todos with filtering and sorting
  - Create new tasks with tags and due dates
  - Toggle todo status (pending → completed ↔ pending)
  - Cancel and restore tasks
  - Soft-delete tasks

Architecture (SOLID + Factory Pattern):
  - TodoApp: Handles UI rendering and user interactions (View layer)
  - Repositories/UnitOfWork: Handle data access (Data layer)
  - Factory: Creates repositories without hardcoding implementations
  - DbState: Tracks dirty state for lock management on shutdown

Database Lock:
  - Acquired on startup to prevent concurrent writes
  - Released on clean shutdown (only if no uncommitted changes)
  - Can be force-unlocked with --force-unlock flag

Keyboard Bindings:
  j/k: Cursor up/down
  x: Toggle done status
  c: Cancel task
  u: Restore cancelled/deleted task
  i/a: Insert new task
  /: Filter tasks
  d: Delete (soft) task
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from typing import Iterable

from loguru import logger
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Input, Static

from commands import parse_task_input
from factory import get_unit_of_work_factory
from models import Todo
from unit_of_work import DbState, LockService


STATUS_PENDING = "pending"
"""Task status: pending (not yet completed)."""

STATUS_COMPLETED = "completed"
"""Task status: completed (task finished)."""

STATUS_CANCELLED = "cancelled"
"""Task status: cancelled (task abandoned without completion)."""


class StatusBar(Static):
    """Status display widget for TUI footer.

    Displays application status messages (e.g., errors, confirmations).
    Uses Textual Static widget for simple text rendering.
    """

    pass


class TodoApp(App):
    """Terminal User Interface for todo management.

    Single Responsibility: Render UI and handle user interactions.
    Delegates data access to UnitOfWork + Repository pattern.

    Lifecycle:
      1. __init__: Initialize app state and configuration
      2. compose: Build widget hierarchy (DataTable, Inputs, etc)
      3. on_mount: Initialize table columns and load initial data
      4. User interaction: Action methods handle keybindings
      5. Data flow: Actions → repository calls → refresh_table()

    State:
      - DbState: Tracks dirty flag (uncommitted changes)
      - filter_text: Current filter query (e.g., 'status:pending')

    Architecture:
      - No business logic: filters/parsing delegated to repositories
      - No database calls: all I/O via UnitOfWork factory
      - Stateless UI: refreshes table after each mutation

    Attributes:
        CSS: Textual CSS for widget styling.
        BINDINGS: Keyboard shortcuts and their action methods.
    """

    CSS = """
    Screen { padding: 1; }
    #inputs { height: 3; }
    #task_input { display: none; }
    #filter_input { display: none; }
    #status { height: 1; }
    DataTable:focus > .datatable--cursor {
        background: $accent;
        color: $text;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("j", "cursor_down", "Down"),
        Binding("k", "cursor_up", "Up"),
        Binding("x", "toggle_done", "Toggle"),
        Binding("c", "cancel_task", "Cancel"),
        Binding("u", "restore_task", "Restore"),
        Binding("i", "open_insert", "Insert"),
        Binding("a", "open_insert", "Append"),
        Binding("/", "open_filter", "Filter"),
        Binding("d", "delete_task", "Delete"),
    ]

    def __init__(self, force_unlock: bool = False) -> None:
        """Initialize todo application.

        Args:
            force_unlock: If True, database lock was forcefully acquired.
                          Used to determine lock release behavior on shutdown.
        """
        super().__init__()
        self.force_unlock = force_unlock
        self.state = DbState(dirty=False)
        self.filter_text = "status:pending"

    def compose(self) -> ComposeResult:
        """Build TUI widget hierarchy.

        Creates status bar, data table, input fields, and footer.
        Input fields are hidden by default; shown on user action.

        Yields:
            Textual widgets in rendering order.
        """
        yield StatusBar("PyTodo-TUI")
        with Vertical():
            yield DataTable(id="table")
            with Vertical(id="inputs"):
                yield Input(placeholder="New task", id="task_input")
                yield Input(placeholder="Filter (defaults to work tag)", id="filter_input")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize table on app startup.

        Sets table cursor type, adds column headers, and loads initial todos.
        Called once when app UI is mounted.
        """
        logger.debug("TUI mounted")
        table = self.query_one("#table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Task", "Status", "Tags", "Due", "Created", "Completed")
        self.refresh_table()

    def refresh_table(
        self,
        selected_id: int | None = None,
        selected_row: int | None = None,
    ) -> None:
        """Refresh table with current todos from database.

        Fetches todos from repository using current filter_text.
        Attempts to maintain cursor position at selected_id or selected_row.

        Args:
            selected_id: If provided, move cursor to row with this todo ID.
            selected_row: If provided, move cursor to this row index.
                          selected_id takes precedence.
        """
        logger.debug("Refreshing table")
        table = self.query_one("#table", DataTable)
        table.clear()
        uow_factory = get_unit_of_work_factory()
        with uow_factory() as uow:
            rows = uow.todos.list(self.filter_text or None)
            for todo in rows:
                tags_display = self._format_tags(todo.tags)
                table.add_row(
                    str(todo.id),
                    todo.task,
                    todo.status,
                    tags_display,
                    todo.due_date.isoformat() if todo.due_date else "",
                    self._format_timestamp(todo.created_at),
                    self._format_timestamp(todo.completed_at),
                    key=str(todo.id),
                )
        target_index: int | None = None
        if selected_id is not None:
            target = str(selected_id)
            for index, row in enumerate(table.ordered_rows):
                if str(row.key.value) == target:
                    target_index = index
                    break
        if target_index is None and selected_row is not None and table.row_count:
            target_index = min(selected_row, table.row_count - 1)
        if target_index is not None:
            table.call_after_refresh(self._move_cursor_to_row, target_index)

    def _move_cursor_to_row(self, index: int) -> None:
        """Move cursor to specified row index.

        Bounds-checks index to prevent out-of-range errors.
        Silently returns if table is empty or index is invalid.

        Args:
            index: Row index to move cursor to (0-based).
        """
        table = self.query_one("#table", DataTable)
        if table.row_count == 0:
            return
        if index < 0 or index >= table.row_count:
            return
        table.move_cursor(row=index, animate=False, scroll=False)

    @staticmethod
    def _format_tags(raw_tags: str) -> str:
        """Format tag string for display with rich text markup.

        Parses comma-separated tags and applies visual highlighting.
        Special case: 'urgent' tag is rendered in red.

        Args:
            raw_tags: Comma-separated tag string (e.g., 'work,urgent').

        Returns:
            Formatted tag string with rich text markup (e.g., '[red]urgent[/red]').
        """
        if not raw_tags:
            return ""
        tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]
        rendered: list[str] = []
        for tag in tags:
            if tag.lower() == "urgent":
                rendered.append("[red]urgent[/red]")
            else:
                rendered.append(tag)
        return ",".join(rendered)

    @staticmethod
    def _format_timestamp(value: datetime | None) -> str:
        """Format datetime for display.

        Converts to ISO format with minute-level precision for compact display.
        Returns empty string if value is None.

        Args:
            value: Datetime object or None.

        Returns:
            ISO format string (e.g., '2026-12-25 15:30') or empty string.
        """
        if value is None:
            return ""
        return value.isoformat(sep=" ", timespec="minutes")

    def action_cursor_down(self) -> None:
        """Action: move cursor down one row.

        Delegates to DataTable's built-in action.
        """
        self.query_one("#table", DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Action: move cursor up one row.

        Delegates to DataTable's built-in action.
        """
        self.query_one("#table", DataTable).action_cursor_up()

    def _selected_id(self) -> int | None:
        """Get ID of todo at current cursor position.

        Returns None if table is empty or cursor position is invalid.
        Safely handles IndexError from corrupted cursor state.

        Returns:
            Todo ID (positive integer) or None if no selection.
        """
        table = self.query_one("#table", DataTable)
        if table.row_count == 0:
            return None
        cursor_row = table.cursor_row
        if cursor_row is None:
            return None
        try:
            key = table.ordered_rows[cursor_row].key
        except IndexError:
            return None
        return int(str(key.value))

    def action_toggle_done(self) -> None:
        """Action: toggle todo between pending and completed.

        Transitions status: pending ↔ completed.
        Sets completed_at timestamp when transitioning to completed.
        Clears completed_at when reverting to pending.
        Marks app state as dirty (triggers lock retention on exit).
        """
        todo_id = self._selected_id()
        if todo_id is None:
            return
        table = self.query_one("#table", DataTable)
        selected_row = table.cursor_row
        uow_factory = get_unit_of_work_factory()
        with uow_factory() as uow:
            todo = uow.todos.get(todo_id)
            if todo is None:
                logger.warning("Todo not found for toggle: {id}", id=todo_id)
                return
            todo.status = (
                STATUS_COMPLETED
                if todo.status != STATUS_COMPLETED
                else STATUS_PENDING
            )
            if todo.status == STATUS_COMPLETED:
                todo.completed_at = datetime.utcnow()
            else:
                todo.completed_at = None
            self.state.dirty = True
            logger.debug("Todo toggled: {id}", id=todo_id)
        self.refresh_table(selected_id=todo_id, selected_row=selected_row)

    def action_cancel_task(self) -> None:
        """Action: cancel todo (mark as cancelled status).

        Transitions status to 'cancelled' (different from delete).
        Clears completed_at timestamp.
        Cancelled tasks can be restored with 'u' keybinding.
        """
        todo_id = self._selected_id()
        if todo_id is None:
            return
        table = self.query_one("#table", DataTable)
        selected_row = table.cursor_row
        uow_factory = get_unit_of_work_factory()
        with uow_factory() as uow:
            todo = uow.todos.get(todo_id)
            if todo is None:
                logger.warning("Todo not found for cancel: {id}", id=todo_id)
                return
            todo.status = STATUS_CANCELLED
            todo.completed_at = None
            self.state.dirty = True
            logger.debug("Todo cancelled: {id}", id=todo_id)
        self.refresh_table(selected_id=todo_id, selected_row=selected_row)

    def action_restore_task(self) -> None:
        """Action: restore cancelled or deleted todo.

        Restores from two states:
          - Cancelled (status=cancelled) → status=pending
          - Soft-deleted (is_deleted=True) → is_deleted=False

        Clears completed_at timestamp on restore.
        Silently returns if todo is not cancelled and not deleted.
        """
        todo_id = self._selected_id()
        if todo_id is None:
            return
        table = self.query_one("#table", DataTable)
        selected_row = table.cursor_row
        uow_factory = get_unit_of_work_factory()
        with uow_factory() as uow:
            todo = uow.todos.get(todo_id)
            if todo is None:
                logger.warning("Todo not found for restore: {id}", id=todo_id)
                return
            updated = False
            if todo.is_deleted:
                todo.is_deleted = False
                updated = True
            if todo.status == STATUS_CANCELLED:
                todo.status = STATUS_PENDING
                todo.completed_at = None
                updated = True
            if not updated:
                return
            self.state.dirty = True
            logger.debug("Todo restored: {id}", id=todo_id)
        self.refresh_table(selected_id=todo_id, selected_row=selected_row)

    def action_delete_task(self) -> None:
        """Action: soft-delete todo.

        Sets is_deleted flag without removing row from database.
        Preserves audit trail; deleted tasks can be restored with 'u'.
        Marks app state as dirty.
        """
        todo_id = self._selected_id()
        if todo_id is None:
            return
        table = self.query_one("#table", DataTable)
        selected_row = table.cursor_row
        uow_factory = get_unit_of_work_factory()
        with uow_factory() as uow:
            todo = uow.todos.get(todo_id)
            if todo is None:
                logger.warning("Todo not found for delete: {id}", id=todo_id)
                return
            uow.todos.remove(todo)
            self.state.dirty = True
            logger.debug("Todo deleted: {id}", id=todo_id)
        self.refresh_table(selected_row=selected_row)

    def action_open_insert(self) -> None:
        """Action: open task input field for new todo.

        Clears input field, displays it, and focuses for typing.
        """
        task_input = self.query_one("#task_input", Input)
        task_input.value = ""
        task_input.display = True
        task_input.focus()

    def action_open_filter(self) -> None:
        """Action: open filter input field.

        Populates field with current filter_text and focuses for editing.
        """
        filter_input = self.query_one("#filter_input", Input)
        filter_input.value = self.filter_text
        filter_input.display = True
        filter_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input field submission (Enter key).

        Routes to appropriate handler based on input ID:
          - task_input: Create new todo
          - filter_input: Apply filter query

        Args:
            event: Textual Input.Submitted event.
        """
        if event.input.id == "task_input":
            self._handle_new_task(event.value)
            event.input.display = False
            self.query_one("#table", DataTable).focus()
        if event.input.id == "filter_input":
            self.filter_text = event.value.strip()
            event.input.display = False
            self.query_one("#table", DataTable).focus()
            self.refresh_table()

    def _handle_new_task(self, raw: str) -> None:
        """Handle new task creation from user input.

        Parses input (task description, tags, due date).
        Creates Todo instance and persists via repository.
        Displays error in status bar if parsing fails.
        Marks app state as dirty and refreshes table on success.

        Args:
            raw: Raw input string (e.g., 'Buy milk #shopping @2026-12-25').
        """
        try:
            parsed = parse_task_input(raw)
        except ValueError as exc:
            self.query_one(StatusBar).update(str(exc))
            logger.warning("Task parse failed: {error}", error=str(exc))
            return

        uow_factory = get_unit_of_work_factory()
        with uow_factory() as uow:
            todo = Todo(
                task=parsed.task,
                status=STATUS_PENDING,
                tags=parsed.tags,
                due_date=parsed.due_date,
            )
            uow.todos.add(todo)
            self.state.dirty = True
            logger.debug("Todo added: {task}", task=parsed.task)
        self.refresh_table()


def _acquire_startup_lock(force_unlock: bool) -> None:
    """Acquire distributed database lock on application startup.

    Prevents concurrent writes by multiple app instances.
    If database is locked and force_unlock=False, raises RuntimeError.
    If force_unlock=True, forcefully acquires lock (use with caution).

    Args:
        force_unlock: If True, override existing lock on startup.

    Raises:
        RuntimeError: If database is locked and force_unlock=False.
    """
    logger.debug("Acquiring startup lock")
    LockService().acquire(force=force_unlock)


def _apply_default_tags_to_existing(force: bool = False) -> bool:
    """Apply default tags to existing todos on startup.

    One-time operation: uses app_settings marker to prevent re-running.
    Reads TODO_DEFAULT_TASK_TAGS environment variable.
    Updates untagged active todos with comma-separated default tags.

    Args:
        force: If True, reapply tags even if marker exists (idempotent).

    Returns:
        True if any todos were updated, False otherwise.
    """
    raw = os.getenv("TODO_DEFAULT_TASK_TAGS", "work").strip()
    if not raw:
        return False
    tags = [tag.strip() for tag in raw.split(",") if tag.strip()]
    if not tags:
        return False
    uow_factory = get_unit_of_work_factory()
    with uow_factory() as uow:
        marker = uow.todos.get_setting("default_tags_applied")
        if marker == "1" and not force:
            return False
        updated = uow.todos.apply_default_tags_to_untagged(tags)
        uow.todos.set_setting("default_tags_applied", "1")
    if updated:
        logger.debug("Applied default tags to {count} tasks", count=updated)
    return updated > 0


def _release_if_clean(state: DbState) -> None:
    """Release database lock if no changes were made.

    Lock retention strategy:
      - Dirty session (uncommitted changes): retain lock for crash recovery
      - Clean session (no changes): release lock to unblock other instances

    Args:
        state: DbState instance tracking dirty flag.
    """
    if state.dirty:
        logger.debug("Dirty session, lock retained")
        return
    logger.debug("Releasing lock on clean shutdown")
    LockService().release()


def run(argv: Iterable[str] | None = None) -> None:
    """Run the todo-tui application.

    Entry point for CLI. Handles:
      1. Argument parsing (--force-unlock, --apply-default-tags)
      2. Logger configuration via environment variables
      3. Database lock acquisition
      4. Default tag initialization
      5. TUI app execution
      6. Graceful shutdown with lock release

    Environment variables:
      - TODO_LOG_LEVEL: Log level (default: DEBUG)
      - TODO_LOG_FILE: Log file path (default: pytodo.log)
      - TODO_LOG_ROTATION: Log rotation size (default: 1 MB)
      - TODO_LOG_RETENTION: Log retention duration (default: 7 days)
      - TODO_DEFAULT_TASK_TAGS: Default tags for existing tasks
      - TODO_DB_URL: Database connection URL

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).
    """
    parser = argparse.ArgumentParser(description="PyTodo-TUI")
    parser.add_argument(
        "--force-unlock",
        action="store_true",
        help="Force unlock database",
    )
    parser.add_argument(
        "--apply-default-tags",
        action="store_true",
        help="Apply default tags to existing tasks",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    log_level = os.getenv("TODO_LOG_LEVEL", "DEBUG").upper()
    log_file = os.getenv("TODO_LOG_FILE", "pytodo.log")
    log_rotation = os.getenv("TODO_LOG_ROTATION", "1 MB")
    log_retention = os.getenv("TODO_LOG_RETENTION", "7 days")

    logger.remove()
    logger.add(
        log_file,
        rotation=log_rotation,
        retention=log_retention,
        level=log_level,
        backtrace=True,
        diagnose=False,
    )
    logger.debug("App starting")
    _acquire_startup_lock(args.force_unlock)
    _apply_default_tags_to_existing(force=args.apply_default_tags)

    app = TodoApp(force_unlock=args.force_unlock)
    try:
        app.run()
    finally:
        _release_if_clean(app.state)
        logger.debug("App shutdown")


if __name__ == "__main__":
    """CLI entry point.

    Usage:
        python -m src.main
        uv run todo
    """
    run()
