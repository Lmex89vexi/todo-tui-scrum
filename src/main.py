from __future__ import annotations

import argparse
import os
from typing import Iterable

from loguru import logger
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Input, Static

from commands import parse_task_input
from models import Todo
from unit_of_work import DbState, LockService, SqlAlchemyUnitOfWork


STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"


class StatusBar(Static):
    pass


class TodoApp(App):
    CSS = """
    Screen { padding: 1; }
    #inputs { height: 3; }
    #task_input { display: none; }
    #filter_input { display: none; }
    #status { height: 1; }
    """

    BINDINGS = [
        Binding("j", "cursor_down", "Down"),
        Binding("k", "cursor_up", "Up"),
        Binding("x", "toggle_done", "Toggle"),
        Binding("i", "open_insert", "Insert"),
        Binding("a", "open_insert", "Append"),
        Binding("/", "open_filter", "Filter"),
        Binding("d", "delete_task", "Delete"),
    ]

    def __init__(self, force_unlock: bool = False) -> None:
        super().__init__()
        self.force_unlock = force_unlock
        self.state = DbState(dirty=False)
        self.filter_text = ""

    def compose(self) -> ComposeResult:
        yield StatusBar("PyTodo-TUI")
        with Vertical():
            yield DataTable(id="table")
            with Vertical(id="inputs"):
                yield Input(placeholder="New task", id="task_input")
                yield Input(placeholder="Filter", id="filter_input")
        yield Footer()

    def on_mount(self) -> None:
        logger.debug("TUI mounted")
        table = self.query_one("#table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Task", "Status", "Tags", "Due")
        self.refresh_table()

    def refresh_table(self) -> None:
        logger.debug("Refreshing table")
        table = self.query_one("#table", DataTable)
        table.clear()
        with SqlAlchemyUnitOfWork() as uow:
            rows = uow.todos.list(self.filter_text or None)
            for todo in rows:
                table.add_row(
                    str(todo.id),
                    todo.task,
                    todo.status,
                    todo.tags,
                    todo.due_date.isoformat() if todo.due_date else "",
                    key=str(todo.id),
                )

    def action_cursor_down(self) -> None:
        self.query_one("#table", DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#table", DataTable).action_cursor_up()

    def _selected_id(self) -> int | None:
        table = self.query_one("#table", DataTable)
        if table.row_count == 0:
            return None
        key = table.get_row_key(table.cursor_row)
        if key is None:
            return None
        return int(key)

    def action_toggle_done(self) -> None:
        todo_id = self._selected_id()
        if todo_id is None:
            return
        with SqlAlchemyUnitOfWork() as uow:
            todo = uow.todos.get(todo_id)
            if todo is None:
                logger.warning("Todo not found for toggle: {id}", id=todo_id)
                return
            todo.status = (
                STATUS_COMPLETED
                if todo.status != STATUS_COMPLETED
                else STATUS_PENDING
            )
            self.state.dirty = True
            logger.debug("Todo toggled: {id}", id=todo_id)
        self.refresh_table()

    def action_delete_task(self) -> None:
        todo_id = self._selected_id()
        if todo_id is None:
            return
        with SqlAlchemyUnitOfWork() as uow:
            todo = uow.todos.get(todo_id)
            if todo is None:
                logger.warning("Todo not found for delete: {id}", id=todo_id)
                return
            uow.todos.remove(todo)
            self.state.dirty = True
            logger.debug("Todo deleted: {id}", id=todo_id)
        self.refresh_table()

    def action_open_insert(self) -> None:
        task_input = self.query_one("#task_input", Input)
        task_input.value = ""
        task_input.display = True
        task_input.focus()

    def action_open_filter(self) -> None:
        filter_input = self.query_one("#filter_input", Input)
        filter_input.value = self.filter_text
        filter_input.display = True
        filter_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
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
        try:
            parsed = parse_task_input(raw)
        except ValueError as exc:
            self.query_one(StatusBar).update(str(exc))
            logger.warning("Task parse failed: {error}", error=str(exc))
            return

        with SqlAlchemyUnitOfWork() as uow:
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
    logger.debug("Acquiring startup lock")
    LockService().acquire(force=force_unlock)


def _release_if_clean(state: DbState) -> None:
    if state.dirty:
        logger.debug("Dirty session, lock retained")
        return
    logger.debug("Releasing lock on clean shutdown")
    LockService().release()


def run(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="PyTodo-TUI")
    parser.add_argument(
        "--force-unlock",
        action="store_true",
        help="Force unlock database",
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

    app = TodoApp(force_unlock=args.force_unlock)
    try:
        app.run()
    finally:
        _release_if_clean(app.state)
        logger.debug("App shutdown")


if __name__ == "__main__":
    run()
